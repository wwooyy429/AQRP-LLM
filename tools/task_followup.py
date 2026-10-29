"""Plan bounded follow-up of an existing accepted LEAN task; no network I/O.

The connector dispatcher executes only should_execute=True requests after
list_projects. Reserved requests must never be reissued after an unknown
response. Completed native responses still go through tools/stage2.py.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.engineering_receipts import _native
from qresearch.task_followup import TaskFollowupController, TaskFollowupError
from research import open_registry, read_json


def utc_now():
    return datetime.now(timezone.utc)


def project_ids(envelope):
    if (type(envelope) is not dict or set(envelope) != {"tool_name", "arguments", "result"}
            or envelope["tool_name"] != "mcp__quantconnect__list_projects"
            or type(envelope["arguments"]) is not dict
            or set(envelope["arguments"]) - {"page", "query"}):
        raise TaskFollowupError("An actual list_projects observation is required")
    args = envelope["arguments"]
    if "page" in args and (type(args["page"]) is not int or args["page"] < 1):
        raise TaskFollowupError("Invalid project-list page")
    if "query" in args and (type(args["query"]) is not str or len(args["query"]) > 256):
        raise TaskFollowupError("Invalid project-list query")
    value = _native(envelope["result"])
    if (type(value) is not dict or value.get("success") is not True or value.get("errors")
            or set(value) - {"success", "errors", "projects", "page", "nextPage", "totalPages"}
            or type(value.get("projects")) is not list or len(value["projects"]) > 50):
        raise TaskFollowupError("Project discovery did not return bounded actual IDs")
    for key in ("page", "totalPages"):
        if key in value and (type(value[key]) is not int or value[key] < 1):
            raise TaskFollowupError("Invalid native project pagination")
    if value.get("nextPage") is not None and (type(value["nextPage"]) is not int or value["nextPage"] < 1):
        raise TaskFollowupError("Invalid native next project page")
    ids = []
    for item in value["projects"]:
        if (type(item) is not dict or set(item) - {"projectId", "name", "language"}
                or type(item.get("projectId")) is not int or item["projectId"] <= 0):
            raise TaskFollowupError("Invalid discovered project")
        if "name" in item and (type(item["name"]) is not str or not item["name"].strip()
                or len(item["name"]) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in item["name"])):
            raise TaskFollowupError("Invalid bounded project name")
        if "language" in item and (type(item["language"]) is not str or item["language"] not in {"Py", "C#"}):
            raise TaskFollowupError("Invalid project language")
        ids.append(item["projectId"])
    if len(set(ids)) != len(ids):
        raise TaskFollowupError("Duplicate project discovery is ambiguous")
    return tuple(ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "next", "history", "sync", "status"))
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--projects-file", type=Path)
    parser.add_argument("--tool-file", type=Path)
    args = parser.parse_args(argv)
    if args.projects_file and args.command != "next":
        parser.error("--projects-file belongs only to next")
    if args.tool_file and args.command != "history":
        parser.error("--tool-file belongs only to history")
    controller = TaskFollowupController(open_registry(), read_json(ROOT / "config/task_followup.json"))
    if args.command == "register":
        result = controller.register(args.attempt)
    elif args.command == "next":
        ids = project_ids(read_json(args.projects_file)) if args.projects_file else ()
        if args.projects_file and controller.status(args.attempt)["project_id"] not in ids:
            raise TaskFollowupError("Accepted task project is absent from actual project discovery; stop")
        result = controller.next_action(args.attempt, now=utc_now(), discovered_project_ids=ids)
    elif args.command == "history":
        if not args.tool_file:
            parser.error("--tool-file with the original reserved list_backtests response is required")
        result = controller.record_history(args.attempt, read_json(args.tool_file))
    elif args.command == "sync":
        result = controller.sync(args.attempt)
    else:
        result = controller.status(args.attempt)
    print(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
