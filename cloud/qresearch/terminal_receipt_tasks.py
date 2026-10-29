"""Bounded native terminal/log/order collection; no provider or budget calls.

A trusted Python host supplies the read authority and already-admitted context.
Neither a directory status nor JSON input can grant permission to read a new
backtest. The journal contains hashes and closed aggregate metadata only. Raw
tool responses remain in the trusted transport's cloud receipt source; they are
rehydrated and hash-checked before the existing fixed completion parser runs.
This operational boundary is not remote authentication or independent approval.
"""
from dataclasses import asdict, dataclass
import json
import math
import re
from uuid import uuid4

from .artifacts import canonical_json, content_hash, decode_events
from .engineering_receipts import (_CHUNK, _context, _native, _tool,
                                   backtest_observation)

PROJECTS = "mcp__quantconnect__list_projects"
READ = "mcp__quantconnect__read_backtest"
LOGS = "mcp__quantconnect__search_backtest_logs"
ORDERS = "mcp__quantconnect__read_backtest_orders"
MAX_OBSERVATION_BYTES = 2 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}")
_ID = re.compile(r"[0-9a-f]{32}")


def _require(condition):
    if not condition:
        raise ValueError("Invalid terminal receipt boundary")


def _same(left, right):
    return canonical_json(left) == canonical_json(right)


@dataclass(frozen=True)
class TerminalReadAuthority:
    """Trusted installation input; never constructed from stdin/LLM proposals.

    Evidence digest binds the real delivery/reference checked by the operator;
    the digest itself does not prove who delivered it. Historical directory
    completion and elapsed time deliberately are not grant bases.
    """
    attempt_id: str
    project_id: int
    backtest_id: str
    basis: str
    evidence_sha256: str

    def __post_init__(self):
        _require(type(self.attempt_id) is str and _ID.fullmatch(self.attempt_id)
                 and type(self.project_id) is int and self.project_id > 0
                 and type(self.backtest_id) is str and 0 < len(self.backtest_id) <= 256
                 and not any(ord(c) < 32 for c in self.backtest_id)
                 and self.basis in {"delivered_terminal_notification", "historical_user_reference"}
                 and type(self.evidence_sha256) is str and _HASH.fullmatch(self.evidence_sha256))


class TerminalReceiptCollector:
    """At most once for every request, with no automatic retry after ambiguity.

    ``receipt_source(digest)`` must retrieve the original already-observed tool
    envelope, not make a remote call. This class never stores native panels,
    source rows, order rows, error strings or encoded log chunks locally.
    """
    def __init__(self, payload=None, deployment=None, backtest_id=None, *, store=None,
                 authority=None, enabled=False, max_log_pages=8,
                 receipt_source=None, bridge=None):
        _require(type(enabled) is bool)
        self.enabled = enabled
        if not enabled:
            return  # Off mode must not inspect a store, Registry or payload.
        _require(type(authority) is TerminalReadAuthority
                 and type(max_log_pages) is int and 1 <= max_log_pages <= 8)
        payload, deployment = _context(payload, deployment, "lean")
        identity = payload["identity"]
        _require((authority.attempt_id, authority.project_id, authority.backtest_id)
                 == (identity["attempt_id"], identity["project_id"], backtest_id))
        self._payload_bytes = canonical_json(payload)
        self._deployment_bytes = canonical_json(deployment)
        self._backtest_id, self._max_log_pages = backtest_id, max_log_pages
        self.store, self.authority = store, authority
        self.receipt_source, self.bridge = receipt_source, bridge
        self._binding_bytes = canonical_json({"identity": identity, "deployment": deployment,
            "backtest_id": backtest_id, "max_log_pages": max_log_pages,
            "authority_sha256": content_hash(asdict(authority))})
        self.stream = "engineering/terminal-receipts/" + identity["attempt_id"] + "/events.jsonl"
        self.lock = "engineering/terminal-receipts/locks/" + identity["attempt_id"]

    @property
    def payload(self):
        return json.loads(self._payload_bytes)

    @property
    def deployment(self):
        return json.loads(self._deployment_bytes)

    @property
    def binding(self):
        return json.loads(self._binding_bytes)

    @property
    def backtest_id(self):
        return self._backtest_id

    @property
    def max_log_pages(self):
        return self._max_log_pages

    @staticmethod
    def _empty():
        return {"requests": [], "observations": [], "failure": False}

    def _request_for(self, state):
        observations = [row["summary"] for row in state["observations"]]
        if not observations:
            return {"tool_name": PROJECTS, "arguments": {"page": 1}}
        args = {"projectId": self.payload["identity"]["project_id"], "backtestId": self.backtest_id}
        if len(observations) == 1:
            return {"tool_name": READ, "arguments": args}
        if observations[1]["terminal_status"] != "completed":
            return None  # Proven native failure can settle; never invent success proofs.
        if observations[1]["terminal_status"] == "completed":
            logs = [value for value in observations if value["kind"] == "logs"]
            if not logs or len(logs) < logs[0]["total_pages"]:
                return {"tool_name": LOGS, "arguments": dict(args,
                    query="AQRP_ENGINEERING " + self.payload["identity"]["attempt_id"], page=len(logs) + 1)}
        if observations[-1]["kind"] != "orders":
            return {"tool_name": ORDERS, "arguments": dict(args, page=1)}
        return None

    def _validate_summary(self, summary, request, state):
        _require(type(summary) is dict)
        tool = request["tool_name"]
        if tool == PROJECTS:
            _require(_same(summary, {"kind": "projects", "target_present": True}))
        elif tool == READ:
            _require(set(summary) == {"kind", "terminal_status"}
                     and summary["kind"] == "terminal"
                     and summary["terminal_status"] in {"completed", "failed", "runtime_error"})
        elif tool == ORDERS:
            _require(_same(summary, {"kind": "orders", "orders_count": 0}))
        else:
            _require(tool == LOGS and set(summary) == {"kind", "page", "total_pages", "chunk_indexes", "chunk_total"}
                     and summary["kind"] == "logs"
                     and type(summary["page"]) is int and summary["page"] == request["arguments"]["page"]
                     and type(summary["total_pages"]) is int
                     and 1 <= summary["page"] <= summary["total_pages"] <= self.max_log_pages
                     and type(summary["chunk_indexes"]) is list
                     and type(summary["chunk_total"]) is int and 1 <= summary["chunk_total"] <= 128
                     and all(type(v) is int and 0 <= v < summary["chunk_total"] for v in summary["chunk_indexes"])
                     and len(set(summary["chunk_indexes"])) == len(summary["chunk_indexes"]))
            previous = [row["summary"] for row in state["observations"] if row["summary"]["kind"] == "logs"]
            _require(all(row["total_pages"] == summary["total_pages"]
                         and row["chunk_total"] == summary["chunk_total"] for row in previous))
            old_indexes = [index for row in previous for index in row["chunk_indexes"]]
            combined = old_indexes + summary["chunk_indexes"]
            _require(len(set(combined)) == len(combined))
            if summary["page"] == summary["total_pages"]:
                _require(set(combined) == set(range(summary["chunk_total"])))

    def _load(self):
        state = self._empty()
        if not self.store.exists(self.stream):
            return state
        events = decode_events(self.store.read_bytes(self.stream))
        _require(bool(events) and _same(events[0]["event"], {"kind": "bound", "binding": self.binding}))
        for wrapped in events[1:]:
            event = wrapped["event"]
            _require(not state["failure"])
            if event.get("kind") == "reserved":
                _require(set(event) == {"kind", "correlation_id", "request"}
                         and type(event["correlation_id"]) is str and _ID.fullmatch(event["correlation_id"])
                         and len(state["requests"]) == len(state["observations"])
                         and _same(event["request"], self._request_for(state))
                         and all(row["correlation_id"] != event["correlation_id"] for row in state["requests"]))
                state["requests"].append(event)
            elif event.get("kind") in {"observed", "rejected"}:
                expected = {"kind", "correlation_id", "envelope_sha256"}
                if event["kind"] == "observed":
                    expected.add("summary")
                _require(set(event) == expected and len(state["requests"]) == len(state["observations"]) + 1
                         and event["correlation_id"] == state["requests"][-1]["correlation_id"]
                         and type(event["envelope_sha256"]) is str and _HASH.fullmatch(event["envelope_sha256"]))
                if event["kind"] == "rejected":
                    state["failure"] = True
                else:
                    self._validate_summary(event["summary"], state["requests"][-1]["request"], state)
                    state["observations"].append(event)
            else:
                _require(False)
        return state

    def _status(self, state):
        if state["failure"]:
            action = "attention_required"
        elif len(state["requests"]) > len(state["observations"]):
            action = "reserved_response_unknown"
        elif self._request_for(state) is None:
            action = "ready_for_reconciliation"
        else:
            action = "ready_for_next_request"
        return {"schema_version": 1, "type": "status", "action": action,
                "should_execute": False, "attempt_id": self.payload["identity"]["attempt_id"]}

    def status(self):
        if not self.enabled:
            return {"schema_version": 1, "type": "status", "action": "dispatch_disabled", "should_execute": False}
        with self.store.locked(self.lock):
            return self._status(self._load())

    def prepare(self):
        if not self.enabled:
            return self.status()
        with self.store.locked(self.lock):
            state = self._load()
            status = self._status(state)
            if status["action"] != "ready_for_next_request":
                return status
            if not self.store.exists(self.stream):
                self.store.append_event(self.stream, {"kind": "bound", "binding": self.binding})
            request = self._request_for(state)
            correlation = uuid4().hex
            self.store.append_event(self.stream, {"kind": "reserved", "correlation_id": correlation, "request": request})
            return dict(request, schema_version=1, type="tool_request", correlation_id=correlation,
                        attempt_id=self.payload["identity"]["attempt_id"])

    def _summary(self, envelope, request):
        _require(len(canonical_json(envelope)) <= MAX_OBSERVATION_BYTES
                 and envelope["tool_name"] == request["tool_name"] and _same(envelope["arguments"], request["arguments"]))
        name = request["tool_name"]
        if name == PROJECTS:
            native = _native(envelope["result"])
            _require(type(native) is dict and not set(native) - {"success", "errors", "projects", "page", "nextPage", "totalPages"}
                     and native.get("success") is True and native.get("errors") in (None, [])
                     and type(native.get("projects")) is list and len(native["projects"]) <= 50)
            _require(("page" not in native or type(native["page"]) is int and native["page"] == 1)
                     and ("totalPages" not in native or type(native["totalPages"]) is int and native["totalPages"] >= 1)
                     and ("nextPage" not in native or native["nextPage"] is None
                          or type(native["nextPage"]) is int and native["nextPage"] >= 2))
            ids = []
            for row in native["projects"]:
                _require(type(row) is dict and not set(row) - {"projectId", "name", "language"}
                         and type(row.get("projectId")) is int and row["projectId"] > 0
                         and ("name" not in row or type(row["name"]) is str)
                         and ("language" not in row or row["language"] in {"Py", "C#"}))
                ids.append(row["projectId"])
            _require(len(set(ids)) == len(ids) and self.payload["identity"]["project_id"] in ids)
            return {"kind": "projects", "target_present": True}
        if name == ORDERS:
            native = _native(envelope["result"])
            _require(type(native) is dict and not set(native) - {"success", "errors", "orders", "totalOrders", "totalPages"}
                     and native.get("success") is True and native.get("errors") in (None, [])
                     and type(native.get("orders")) is list and native["orders"] == []
                     and type(native.get("totalOrders")) is int and native["totalOrders"] == 0
                     and ("totalPages" not in native or type(native["totalPages"]) is int and native["totalPages"] in {0, 1}))
            return {"kind": "orders", "orders_count": 0}
        native, _ = _tool(envelope, name, self.payload, external_id=self.backtest_id, allow_tool_error=name == READ)
        if name == LOGS:
            _require(type(native) is dict and not set(native) - {"success", "errors", "logs", "totalPages"}
                     and native.get("success") is True and native.get("errors") in (None, [])
                     and type(native.get("logs")) is list and 0 < len(native["logs"]) <= 128)
            indexes, totals = [], []
            for line in native["logs"]:
                _require(type(line) is str)
                match = _CHUNK.search(line)
                _require(match is not None and line.count("AQRP_ENGINEERING") == 1
                         and match[1] == self.payload["identity"]["attempt_id"])
                index, total, chunk = int(match[2]), int(match[3]), match[4]
                _require(str(index) == match[2] and str(total) == match[3]
                         and 1 <= total <= 128 and 0 <= index < total
                         and len(chunk) <= 500
                         and (index == total - 1 or len(chunk) == 500))
                indexes.append(index); totals.append(total)
            _require(len(set(totals)) == 1)
            return {"kind": "logs", "page": request["arguments"]["page"], "total_pages": native.get("totalPages"),
                    "chunk_indexes": indexes, "chunk_total": totals[0]}
        if envelope["result"].get("isError") is True:
            parsed = backtest_observation(self.payload, self.deployment, self.backtest_id, envelope, [])
            return {"kind": "terminal", "terminal_status": parsed["platform"]["status"]}
        _require(type(native) is dict and native.get("success") is True and not native.get("errors"))
        backtest = native.get("backtest")
        _require(type(backtest) is dict and type(backtest.get("projectId")) is int
                 and backtest["projectId"] == self.payload["identity"]["project_id"]
                 and backtest.get("backtestId") == self.backtest_id
                 and type(backtest.get("completed")) is bool
                 and type(backtest.get("hasInitializeError", False)) is bool
                 and type(backtest.get("progress")) in {int, float} and math.isfinite(backtest["progress"])
                 and 0 <= backtest["progress"] <= 1
                 and all(backtest.get(key) is None or type(backtest[key]) is str for key in ("error", "stacktrace")))
        if backtest.get("status") == "Runtime Error" or backtest.get("error") or backtest.get("stacktrace") or backtest.get("hasInitializeError"):
            parsed = backtest_observation(self.payload, self.deployment, self.backtest_id, envelope, [])
            _require(parsed["platform"]["status"] in {"failed", "runtime_error"})
            return {"kind": "terminal", "terminal_status": parsed["platform"]["status"]}
        _require(backtest.get("status") == "Completed." and backtest["completed"] is True and backtest["progress"] == 1)
        return {"kind": "terminal", "terminal_status": "completed"}

    def accept_response(self, message):
        if not self.enabled:
            return self.status()
        message = json.loads(canonical_json(message))
        _require(type(message) is dict and set(message) == {"command", "attempt_id", "correlation_id", "tool_name", "arguments", "result"}
                 and message["command"] == "response" and message["attempt_id"] == self.payload["identity"]["attempt_id"])
        envelope = {key: message[key] for key in ("tool_name", "arguments", "result")}
        digest = content_hash(envelope)
        with self.store.locked(self.lock):
            state = self._load()
            for row in state["observations"]:
                if row["correlation_id"] == message["correlation_id"]:
                    _require(row["envelope_sha256"] == digest)
                    return self._status(state)
            _require(not state["failure"] and len(state["requests"]) == len(state["observations"]) + 1)
            reserved = state["requests"][-1]
            _require(message["correlation_id"] == reserved["correlation_id"]
                     and envelope["tool_name"] == reserved["request"]["tool_name"]
                     and _same(envelope["arguments"], reserved["request"]["arguments"]))
            try:
                summary = self._summary(envelope, reserved["request"])
                self._validate_summary(summary, reserved["request"], state)
            except (ValueError, TypeError, KeyError, OverflowError):
                self.store.append_event(self.stream, {"kind": "rejected", "correlation_id": message["correlation_id"], "envelope_sha256": digest})
                return self._status(self._load())
            self.store.append_event(self.stream, {"kind": "observed", "correlation_id": message["correlation_id"], "envelope_sha256": digest, "summary": summary})
            return self._status(self._load())

    def reconcile(self, receipt_source=None):
        """Retrieve already observed receipts, validate all, return safe output."""
        _require(self.enabled)
        source = self.receipt_source if receipt_source is None else receipt_source
        _require(callable(source))
        with self.store.locked(self.lock):
            state = self._load()
            _require(self._status(state)["action"] == "ready_for_reconciliation")
            request_rows = list(state["requests"]); rows = list(state["observations"])
        envelopes = []
        replay = self._empty()
        for request, observed in zip(request_rows, rows):
            envelope = json.loads(canonical_json(source(observed["envelope_sha256"])))
            _require(content_hash(envelope) == observed["envelope_sha256"])
            summary = self._summary(envelope, request["request"])
            _require(_same(summary, observed["summary"]))
            self._validate_summary(summary, request["request"], replay)
            replay["observations"].append(observed)
            envelopes.append(envelope)
        parsed = backtest_observation(self.payload, self.deployment, self.backtest_id,
            envelopes[1], [value for value in envelopes if value["tool_name"] == LOGS])
        order_rows = [row for row in rows if row["summary"]["kind"] == "orders"]
        completed = rows[1]["summary"]["terminal_status"] == "completed"
        return {"completion": parsed, "zero_order_evidence":
                    {"orders_count": 0, "envelope_sha256": order_rows[0]["envelope_sha256"]} if order_rows else None,
                "evidence_collection": {"native_terminal_collected": True,
                    "engineering_logs_collected": any(value["tool_name"] == LOGS for value in envelopes),
                    "independent_zero_orders_collected": bool(order_rows),
                    "success_receipt_chain_complete": completed and bool(order_rows)},
                "same_attempt_settlement_ready": True, "budget_charged": False,
                "independent_acceptance": False, "financial_evidence": False}

    def settle(self, bridge=None, receipt_source=None):
        """Settle only the existing same-attempt bridge; no debit or round close."""
        from .engineering_tasks import EngineeringTaskBridge
        target = self.bridge if bridge is None else bridge
        _require(type(target) is EngineeringTaskBridge)
        attempt = self.payload["identity"]["attempt_id"]
        record = target._record(attempt)
        _require(record["config_id"] == self.payload["identity"]["config_id"]
                 and record["stage"] == "lean" and record["external_id"] == self.backtest_id
                 and _same(target.plan.to_dict(), self.payload["plan"]))
        submission = target._recorded_submission(target.payload(attempt))
        _require(_same(submission["deployment"], self.deployment))
        parsed = self.reconcile(receipt_source)
        return target.consume_completion(attempt, completion_source=lambda _: parsed["completion"])

    def command(self, message):
        _require(type(message) is dict)
        if message.get("command") == "response":
            return self.accept_response(message)
        _require(set(message) == {"command"} and message["command"] in {"wake", "status", "reconcile", "settle"})
        if not self.enabled:
            return self.status()
        if message["command"] == "wake":
            return self.prepare()
        if message["command"] == "status":
            return self.status()
        if message["command"] == "settle":
            return {"attempt": vars(self.settle()), "budget_charged": False}
        return self.reconcile()
