"""Independent synthetic auxiliary checks; no production registry or network."""
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from datetime import timedelta
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "cloud"), str(ROOT / "tools"), str(ROOT / "tests")]
from qresearch.artifacts import FilesystemArtifactStore
from qresearch.registry import Registry
from qresearch.task_followup import TaskFollowupController, TaskFollowupError
from test_task_followup import fixture, history, POLICY, DEADLINE

LIMITS = {kind: {"total": 10, "normal": 8, "reserve": 2}
          for kind in ("configurations", "research", "lean")}


def concurrent_reserve(args):
    directory, attempt = args
    store = FilesystemArtifactStore(directory, data_classification="synthetic", lock_timeout=20)
    registry = Registry(store, LIMITS)
    return TaskFollowupController(registry, POLICY).next_action(
        attempt, now=DEADLINE, discovered_project_ids=(17,))


def deny_delete_temporarily(path, ready):
    """A real Windows sharing handle, not a mocked PermissionError."""
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.CreateFileW(str(path), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    ready.set()
    time.sleep(0.4)
    if not api.CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def main():
    results = []
    # Real OS file sharing exercises winerror=32 without patching the release
    # implementation, global clock, pathlib or error type.
    with tempfile.TemporaryDirectory(prefix="aqrp-sharing-synthetic-") as directory:
        store_fs = FilesystemArtifactStore(directory, data_classification="synthetic", lock_timeout=2)
        ready = multiprocessing.Event()
        bodies = 0
        with store_fs.locked("synthetic/external-reader"):
            bodies += 1
            lock = next((Path(directory) / ".locks").iterdir())
            worker = multiprocessing.Process(target=deny_delete_temporarily, args=(lock, ready))
            worker.start()
            assert ready.wait(10), "Synthetic reader did not open the lock"
            started = time.monotonic()
        elapsed = time.monotonic() - started
        worker.join(10)
        assert worker.exitcode == 0 and not worker.is_alive()
        assert 0.25 <= elapsed < 2 and bodies == 1 and not lock.exists()
        results.append({"check": "real Windows delete-sharing violation", "body_executions": bodies,
                        "release_seconds": round(elapsed, 3), "lock_released": True})
    # Existing unit tests use the in-memory lock. Exercise true Windows
    # cooperating process contention against independently opened stores.
    store, registry, bridge, attempt, controller = fixture()
    journal = store.read_bytes(registry.JOURNAL)
    with tempfile.TemporaryDirectory(prefix="aqrp-followup-synthetic-") as directory:
        target = Path(directory)
        for key, value in store._data.items():
            path = target.joinpath(*key.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
        with ProcessPoolExecutor(max_workers=6) as pool:
            calls = list(pool.map(concurrent_reserve, [(directory, attempt)] * 18))
        assert sum(call["should_execute"] for call in calls) == 1
        assert all(call["action"] == "attention_required" for call in calls if not call["should_execute"])
        fresh = FilesystemArtifactStore(directory, data_classification="synthetic")
        assert fresh.read_bytes(registry.JOURNAL) == journal
        assert not list((target / ".locks").iterdir())
        results.append({"check": "18 requests / 6 independent Windows processes", "dispatches": 1,
                        "registry_unchanged": True, "leaked_locks": 0})

    # A foreign task's Completed status must never authorize reading our target.
    store, registry, bridge, attempt, controller = fixture()
    before = store.read_bytes(registry.JOURNAL)
    controller.next_action(attempt, now=DEADLINE, discovered_project_ids=(17,))
    controller.record_history(attempt, history(backtest="foreign-completed-task", total=1))
    result = controller.next_action(attempt, now=DEADLINE + timedelta(days=30), discovered_project_ids=(17,))
    assert result["action"] == "attention_required" and not result["should_execute"]
    assert store.read_bytes(registry.JOURNAL) == before
    results.append({"check": "foreign terminal task / long later restart", "dispatches": 0,
                    "registry_unchanged": True})

    # Invalid original output must leave the page unknown; no alternate tool,
    # payload-carrier or large elapsed-time route may turn it into another read.
    store, registry, bridge, attempt, controller = fixture()
    before = store.read_bytes(registry.JOURNAL)
    controller.next_action(attempt, now=DEADLINE, discovered_project_ids=(17,))
    original = store.read_bytes(controller._stream(attempt))
    invalid = history()
    invalid["result"]["content"].append({"type": "text", "text": "SYNTHETIC hidden carrier"})
    try:
        controller.record_history(attempt, invalid)
    except TaskFollowupError:
        pass
    else:
        raise AssertionError("Additional output carrier accepted")
    assert original == store.read_bytes(controller._stream(attempt))
    restarted = TaskFollowupController(registry, deepcopy(POLICY))
    result = restarted.next_action(attempt, now=DEADLINE + timedelta(days=30), discovered_project_ids=(17,))
    assert result["action"] == "attention_required" and not result["should_execute"]
    assert store.read_bytes(registry.JOURNAL) == before
    results.append({"check": "hidden carrier -> unknown response -> long later restart", "dispatches": 0,
                    "registry_unchanged": True})

    # Report return-value semantics separately without treating it as a defect:
    # registration/sync are bookkeeping, while status/next expose dispatch risk.
    semantic = {"register": restarted.register(attempt)["action"],
                "sync": restarted.sync(attempt)["action"],
                "status": restarted.status(attempt)["action"],
                "next": result["action"]}
    results.append({"check": "unknown-response API return semantics", "actions": semantic})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
