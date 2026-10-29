from pathlib import Path
import json
import os
import sys
import traceback

root = Path(sys.argv[1]).resolve()
out = Path(__file__).resolve().parent
sys.path[:0] = [str(out), str(root / "tools"), str(root / "cloud")]
result = json.loads((out / "results.json").read_text(encoding="utf-8"))
run = Path(result["run_dir"])
evidence = []
for entry in ("canonical", "module"):
    request = json.loads(next(x["stdout"] for x in result["subprocesses"] if x["label"] == entry + "-wake"))
    os.environ.update(WR29_STORE=str(run / "stores" / (entry + "-restart")), WR29_ATTEMPT=request["attempt_id"],
        WR29_CLOCK_USED=str(run / "diagnostic-clock-used.txt"), WR29_METADATA=str(run / (entry + "-diagnostic-meta.json")))
    import wr29_boundary_factory
    host = wr29_boundary_factory.build()
    native = dict(success=True, projects=[dict(projectId=17, name="SYNTHETIC_WR29", language="Py")], page=1, nextPage=None, totalPages=1)
    response = dict(command="response", **{k: request[k] for k in ("attempt_id", "correlation_id", "tool_name", "arguments")},
        result=dict(structuredContent=native, content=[dict(type="text", text=json.dumps(native))], isError=False))
    try:
        outcome = host.accept_response(response)
        evidence.append(dict(entry=entry, outcome=outcome))
    except Exception:
        evidence.append(dict(entry=entry, traceback=traceback.format_exc()))
(out / "late-response-diagnostic.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(evidence, ensure_ascii=False, indent=2))
