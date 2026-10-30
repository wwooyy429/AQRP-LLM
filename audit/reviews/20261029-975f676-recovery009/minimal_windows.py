from pathlib import Path
from hashlib import sha256
from tempfile import TemporaryDirectory
from threading import Timer
from ctypes import wintypes
import ctypes, sys, os

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(sys.argv[1]).resolve() / 'cloud'))
from qresearch.artifacts import FilesystemArtifactStore
from qresearch.task_followup import validate_policy, TaskFollowupError

policy = {'schema_version': 1, 'notification_grace_seconds': 1800, 'max_history_pages': 3}
assert validate_policy(policy) == policy
try:
    validate_policy(policy | {'max_history_pages': 4})
except TaskFollowupError:
    pass
else:
    raise AssertionError('Unbounded policy accepted')

assert os.name == 'nt', 'This reproduction requires actual Windows'
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel.CreateFileW.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.CloseHandle.restype = wintypes.BOOL

with TemporaryDirectory() as temporary:
    root = Path(temporary)
    store = FilesystemArtifactStore(root, lock_timeout=1)
    key, body_count = 'independent/minimal', 0
    lock = root / '.locks' / (sha256(key.encode()).hexdigest() + '.lock')
    with store.locked(key):
        body_count += 1
        handle = kernel.CreateFileW(str(lock), 0x80000000, 3, None, 3, 0x80, None)
        assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
        try:
            lock.unlink()
        except OSError as error:
            assert error.winerror == 32
        else:
            raise AssertionError('Expected native WinError32')
        timer = Timer(0.15, lambda: kernel.CloseHandle(handle))
        timer.start()
    timer.join()
    assert body_count == 1 and not lock.exists()
print('PASS: strict follow-up policy; actual WinError32 recovered; body executed once')
