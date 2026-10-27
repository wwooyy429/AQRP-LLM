from io import BytesIO
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
COMMIT = "ccad61d03ccf17bf2bdc2d7ffc88dfd11b6d3ca6"
BASELINE = "ea6053e3e9ef4be17db246daf18a4cf9b2e5be58"
ORIGINAL = Path("B:/BaiduSyncdisk/学习/投资/量化/量化交易比赛/LLM审核/review-ccad61d-20261027/archive_agent/minimal_wr27_root_manifest.py")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def materialize(destination):
    verification = json.loads(subprocess.check_output(["git", "show", COMMIT + ":audit/stage_verification.json"], cwd=ROOT))
    names = sorted(set(verification["source_files"]) | {"audit/stage2_current_readiness.json", "audit/runtime/registry/events.jsonl"})
    requests = "".join(COMMIT + ":" + name + "\n" for name in names).encode("utf-8")
    stream = BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=requests, cwd=ROOT))
    for name in names:
        header = stream.readline().split()
        assert len(header) == 3 and header[1] == b"blob", name
        raw = stream.read(int(header[2])); assert stream.read(1) == b"\n"
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    assert not stream.read()


def run(kind):
    source = OUT / (kind + "_source")
    if source.exists():
        raise ValueError("Use a fresh MRE source directory; earlier evidence is not replaced")
    materialize(source)
    original_copy = OUT / "minimal_wr27_root_manifest.original.py"
    if not original_copy.exists():
        shutil.copyfile(ORIGINAL, original_copy)
    assert original_copy.read_bytes() == ORIGINAL.read_bytes()
    script = original_copy
    adaptations = []
    if kind == "fixed":
        for name in ("tools/stages.py", "tools/review_metadata.py", "tests/test_review_metadata.py"):
            shutil.copyfile(ROOT / name, source / name)
        spec = importlib.util.spec_from_file_location("wr27_original_helper", original_copy)
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        gitdir = subprocess.check_output(["git", "rev-parse", "--absolute-git-dir"], cwd=ROOT, text=True).strip()
        private_index = OUT / "fixed_prepare.index"
        env = dict(os.environ, GIT_DIR=gitdir, GIT_WORK_TREE=str(source), GIT_INDEX_FILE=str(private_index), GIT_OPTIONAL_LOCKS="0")
        subprocess.run(["git", "read-tree", COMMIT], cwd=ROOT, env=env, capture_output=True, check=True)
        names = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", BASELINE, "--", "cloud", "tests", "tools"], cwd=ROOT, env=env, text=True).splitlines()
        metadata_path = source / "audit/stage2_current_readiness.json"
        metadata = json.loads(metadata_path.read_bytes())
        metadata["source_changed_this_round"] = sorted(name for name in names if name.endswith(".py"))
        metadata["candidate_source_manifest_hash"] = digest(helper.canonical(helper.manifest(source)))
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        raw = original_copy.read_text(encoding="utf-8")
        old = "names=subprocess.check_output(['git','-C',str(a.git_repository),'diff','--name-only','--no-renames',B,C],text=True).splitlines()"
        new = "names=subprocess.check_output(['git','-C',str(a.git_repository),'diff','--name-only','--no-renames',B],text=True,env=env).splitlines()"
        assert raw.count(old) == 1
        script = OUT / "minimal_wr27_root_manifest.fixed_scope.py"
        script.write_text(raw.replace(old, new), encoding="utf-8", newline="\n")
        adaptations = ["Current-product files overlaid on a fresh raw ccad snapshot; no real ledger or configuration changes",
            "Source metadata hash and changed-path set recomputed for the isolated overlaid tree",
            "Original B..C fixed diff changed in separate script to B..working-tree under the original private Git index/work-tree environment; all assertions unchanged",
            "Original C remains a historical base-snapshot label; actual product file hashes recorded below"]
    cmd = [sys.executable, "-B", str(script), "--source", str(source), "--git-repository", str(ROOT), "--output", str(OUT / (kind + "_mre"))]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True)
    (OUT / (kind + ".stdout")).write_bytes(result.stdout)
    (OUT / (kind + ".stderr")).write_bytes(result.stderr)
    observation = json.loads((OUT / (kind + "_mre/result.json")).read_bytes())
    report = {"command": cmd, "exit_code": result.returncode, "base_snapshot": COMMIT,
        "original_script_raw_sha256": digest(original_copy.read_bytes()), "original_script_unchanged": original_copy.read_bytes() == ORIGINAL.read_bytes(),
        "adaptations": adaptations, "actual_product_raw_sha256": {name: digest((source / name).read_bytes()) for name in ("tools/stages.py", "tools/review_metadata.py", "tests/test_review_metadata.py")},
        "observed": observation, "new_platform_calls": 0, "real_ledger_or_budget_writes": 0, "independent_acceptance": False}
    (OUT / (kind + "_execution.json")).write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="ascii")
    print(json.dumps({"kind": kind, "exit_code": result.returncode, "default_exit": observation["default_legal_control_exit"],
        "foreign_hash_exit": observation["foreign_hash_actual_exit"], "own_hash_exit": observation["own_hash_actual_exit"],
        "original_script_unchanged": report["original_script_unchanged"]}))
    assert result.returncode == (1 if kind == "baseline" else 0)
    assert observation["default_legal_control_exit"] == 0
    assert observation["foreign_hash_actual_exit"] == (0 if kind == "baseline" else 1)
    assert observation["own_hash_actual_exit"] == (1 if kind == "baseline" else 0)


if __name__ == "__main__":
    run(sys.argv[1])
