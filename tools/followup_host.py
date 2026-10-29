"""Executable JSON-lines host for one fixed, already accepted LEAN attempt.

Default CLI operation is off and does not open a Registry. Production embedding
injects a TaskFollowupController and trusted transport authority in Python, or
supplies a trusted zero-argument factory with --enable-dispatch --host-factory.
stdin cannot grant authority, change clocks, or supply arbitrary requests.

serve accepts {command: wake|register|sync|status, attempt_id: ...} and responses
with command=response, attempt_id, correlation_id, tool_name, arguments, result.
Every emitted tool_request is durable BEFORE stdout/client dispatch. A restart,
lost stdout or lost response never re-emits it. The original bound response can
still arrive later. The upstream transport retains native responses securely;
this host stores hashes/closed metadata only. read_backtest hands off to the
existing stage2 backtest-result parser (including logs/zero-order checks), and
does not claim to settle the Registry or automate the complete receipt chain.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
from pathlib import Path
import re
import math
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "cloud"))
from qresearch.artifacts import canonical_json, content_hash, decode_events
from qresearch.engineering_receipts import _native
from qresearch.task_followup import TaskFollowupController
from task_followup import project_ids

PROJECTS = "mcp__quantconnect__list_projects"
HISTORY = "mcp__quantconnect__list_backtests"
READ = "mcp__quantconnect__read_backtest"
MAX_LINE = 2 * 1024 * 1024
_HASH = re.compile(r"[0-9a-f]{64}")
_ATTEMPT = re.compile(r"[0-9a-f]{32}")
_FAILURES = {"response_binding_rejected", "response_conflict", "invalid_native_response",
             "project_not_discovered", "discovery_not_authorized", "history_not_authorized",
             "completed_read_not_authorized", "watch_registration_failed"}
_OUTCOMES = {"projects_observed", "history_observed", "awaiting_native_receipt", "rejected"}


def utc_now():
    return datetime.now(timezone.utc)


def strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = item
        return result
    def invalid(_):
        raise ValueError("nonfinite_json")
    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid)


def _attempt(value):
    if type(value) is not str or not _ATTEMPT.fullmatch(value):
        raise ValueError("invalid_attempt")
    return value


def _hash(value):
    return type(value) is str and _HASH.fullmatch(value) is not None


def _status(attempt, action, failure_code=None):
    result = {"schema_version": 1, "type": "status", "attempt_id": attempt,
              "action": action, "should_execute": False}
    if failure_code:
        result["failure_code"] = failure_code
    if action == "awaiting_native_receipt":
        result["receipt_parser"] = "tools/stage2.py backtest-result"
    return result


@dataclass(frozen=True)
class ReadGrant:
    """Trusted host evidence, never accepted from JSON-lines/LLM proposals.

    A directory observation is deliberately not an admissible grant basis.
    transport_completed_reads is valid only for a transport explicitly permitting
    such reads. Chat connector reads require actual delivered terminal notification
    or the user's historical task reference, bound to this exact task.
    """
    attempt_id: str
    project_id: int
    backtest_id: str
    basis: str
    evidence_sha256: str


@dataclass(frozen=True)
class TransportAuthority:
    transport_name: str
    discovery_attempts: frozenset = frozenset()
    history_attempts: frozenset = frozenset()
    read_mode: str = "disabled"
    read_grants: tuple = ()

    def __post_init__(self):
        if (type(self.transport_name) is not str or not self.transport_name.strip()
                or len(self.transport_name) > 128 or any(ord(c) < 32 for c in self.transport_name)
                or type(self.discovery_attempts) is not frozenset
                or type(self.history_attempts) is not frozenset
                or type(self.read_grants) is not tuple
                or self.read_mode not in {"disabled", "chat_connector", "completion_reads_permitted"}):
            raise ValueError("invalid_transport_authority")
        for attempt in self.discovery_attempts | self.history_attempts:
            _attempt(attempt)
        for grant in self.read_grants:
            if (type(grant) is not ReadGrant or not _hash(grant.evidence_sha256)
                    or type(grant.project_id) is not int or grant.project_id <= 0
                    or type(grant.backtest_id) is not str or not grant.backtest_id
                    or len(grant.backtest_id) > 256
                    or grant.basis not in {"delivered_terminal_notification", "historical_user_reference",
                                           "transport_completed_reads"}):
                raise ValueError("invalid_read_grant")
            _attempt(grant.attempt_id)

    def permits_read(self, identity):
        if self.read_mode == "disabled":
            return False
        return any(grant.attempt_id == identity["attempt_id"]
                   and grant.project_id == identity["project_id"]
                   and grant.backtest_id == identity["backtest_id"]
                   and (grant.basis != "transport_completed_reads"
                        or self.read_mode == "completion_reads_permitted")
                   for grant in self.read_grants)


class FollowupHost:
    """Small at-most-once host. Its lock is separate from Registry.LOCK.

    No call is made while holding Registry.LOCK. The host lock serializes host
    decisions across processes; controller methods acquire their own short
    Registry transaction. A crash between the two durable reservations is safe:
    controller.next then returns attention and no request can be reconstructed.
    """
    LOCK = "engineering/followup-host/LOCK"

    def __init__(self, controller=None, *, authority=None, enabled=False, clock=None):
        if type(enabled) is not bool:
            raise ValueError("invalid_dispatch_gate")
        if enabled and (type(controller) is not TaskFollowupController or type(authority) is not TransportAuthority):
            raise ValueError("trusted_controller_and_authority_required")
        self.controller, self.authority, self.enabled = controller, authority, enabled
        # Clock injection is an embedding/test facility; CLI never accepts --now.
        self.clock = utc_now if clock is None else clock
        self.store = controller.store if enabled else None

    @staticmethod
    def _stream(attempt):
        return "engineering/followup-host/" + _attempt(attempt) + "/events.jsonl"

    @staticmethod
    def _identity(result):
        return {key: result[key] for key in ("attempt_id", "project_id", "backtest_id", "submitted_at", "deadline")}

    @staticmethod
    def _request_valid(request, identity):
        if type(request) is not dict or set(request) != {"tool_name", "arguments"}:
            return False
        args, name = request["arguments"], request["tool_name"]
        if type(args) is not dict:
            return False
        if name == PROJECTS:
            return set(args) == {"page"} and type(args["page"]) is int and args["page"] == 1
        if type(args.get("projectId")) is not int or args["projectId"] != identity["project_id"]:
            return False
        if name == HISTORY:
            return set(args) == {"projectId", "page"} and type(args["page"]) is int and 1 <= args["page"] <= 3
        return name == READ and set(args) == {"projectId", "backtestId"} and args["backtestId"] == identity["backtest_id"]

    def _load(self, attempt, identity):
        state = {"requests": {}, "responses": {}, "project_ids": (), "failure": None}
        key = self._stream(attempt)
        if not self.store.exists(key):
            return state
        events = decode_events(self.store.read_bytes(key))
        if not events or events[0]["event"] != {"kind": "bound", "identity": identity}:
            raise ValueError("host_identity_changed")
        seen = set()
        for item in events[1:]:
            event = item["event"]
            kind = event.get("kind")
            if kind == "reserved":
                request = {key: event.get(key) for key in ("tool_name", "arguments")}
                correlation = event.get("correlation_id")
                stamp = datetime.fromisoformat(event["reserved_at"])
                if (set(event) != {"kind", "tool_name", "arguments", "correlation_id", "reserved_at", "decision_hash"}
                        or not self._request_valid(request, identity) or type(correlation) is not str
                        or not _ATTEMPT.fullmatch(correlation) or correlation in state["requests"]
                        or not _hash(event["decision_hash"]) or stamp.tzinfo != timezone.utc
                        or stamp.isoformat() != event["reserved_at"] or state["failure"]
                        or set(state["requests"]) - set(state["responses"])
                        or content_hash(request) in seen):
                    raise ValueError("invalid_host_reservation")
                seen.add(content_hash(request))
                state["requests"][correlation] = request
            elif kind == "response":
                correlation = event.get("correlation_id")
                if (set(event) != {"kind", "correlation_id", "response_hash", "outcome", "project_ids"}
                        or correlation not in state["requests"] or correlation in state["responses"]
                        or not _hash(event["response_hash"]) or event["outcome"] not in _OUTCOMES
                        or type(event["project_ids"]) is not list
                        or any(type(v) is not int or v <= 0 for v in event["project_ids"])
                        or len(event["project_ids"]) > 50 or len(set(event["project_ids"])) != len(event["project_ids"])
                        or (event["outcome"] != "projects_observed" and event["project_ids"])):
                    raise ValueError("invalid_host_response")
                state["responses"][correlation] = event
                if event["outcome"] == "projects_observed":
                    state["project_ids"] = tuple(event["project_ids"])
            elif kind == "attention":
                if (set(event) != {"kind", "failure_code", "response_hash"}
                        or event["failure_code"] not in _FAILURES
                        or (event["response_hash"] is not None and not _hash(event["response_hash"]))):
                    raise ValueError("invalid_host_attention")
                state["failure"] = event["failure_code"]
            else:
                raise ValueError("invalid_host_event")
        return state

    def _append(self, attempt, event):
        self.store.append_event(self._stream(attempt), event)

    def _bind(self, attempt, identity):
        if not self.store.exists(self._stream(attempt)):
            self._append(attempt, {"kind": "bound", "identity": identity})

    def _attention(self, attempt, code, response_hash=None):
        event = {"kind": "attention", "failure_code": code, "response_hash": response_hash}
        # Identical rejected deliveries are idempotent, just like accepted ones.
        if not any(item["event"] == event for item in decode_events(self.store.read_bytes(self._stream(attempt)))):
            self._append(attempt, event)
        return _status(attempt, "attention_required", code)

    def inspect(self, attempt):
        """Read host unknown-response/receipt state without acquiring permission."""
        _attempt(attempt)
        if not self.enabled:
            return _status(attempt, "dispatch_disabled")
        with self.store.locked(self.LOCK):
            current = self.controller.status(attempt)
            if current["action"] == "finished":
                return _status(attempt, "finished")
            state = self._load(attempt, self._identity(current))
            if state["failure"]:
                return _status(attempt, "attention_required", state["failure"])
            if set(state["requests"]) - set(state["responses"]):
                return _status(attempt, "attention_required", "reserved_response_unknown")
            if any(e["outcome"] == "awaiting_native_receipt" for e in state["responses"].values()):
                return _status(attempt, "awaiting_native_receipt")
            return _status(attempt, current["action"])

    def prepare(self, attempt):
        """Reserve and emit ONE request, never reconstruct an outstanding one."""
        _attempt(attempt)
        if not self.enabled:
            return _status(attempt, "dispatch_disabled")
        with self.store.locked(self.LOCK):
            current = self.controller.status(attempt)
            if current["action"] == "finished":
                return _status(attempt, "finished")
            identity = self._identity(current)
            state = self._load(attempt, identity)
            if state["failure"]:
                return _status(attempt, "attention_required", state["failure"])
            if set(state["requests"]) - set(state["responses"]):
                return _status(attempt, "attention_required", "reserved_response_unknown")
            if any(e["outcome"] == "awaiting_native_receipt" for e in state["responses"].values()):
                return _status(attempt, "awaiting_native_receipt")
            # Calling next without project IDs obtains the controller's local
            # permission decision without reserving any connector operation.
            try:
                decision = self.controller.next_action(attempt, now=self.clock())
            except Exception:
                self._bind(attempt, identity)
                return self._attention(attempt, "watch_registration_failed")
            if decision["action"] != "list_projects":
                return _status(attempt, decision["action"])
            if not state["project_ids"]:
                self._bind(attempt, identity)
                if any(r["tool_name"] == PROJECTS for r in state["requests"].values()):
                    return self._attention(attempt, "project_not_discovered")
                if attempt not in self.authority.discovery_attempts:
                    return self._attention(attempt, "discovery_not_authorized")
                request = {"tool_name": PROJECTS, "arguments": {"page": 1}}
            else:
                if attempt not in self.authority.history_attempts:
                    return self._attention(attempt, "history_not_authorized")
                # Check read permission BEFORE next reserves its read. Historical
                # terminal metadata can never override connector restrictions.
                with self.store.locked(self.controller.registry.LOCK):
                    context, record = self.controller._context(self.controller.registry._replay(), attempt)
                    watch = self.controller._load(context, record["status"])
                    target = self.controller._latest(watch).get("target")
                if target and target["status"] in {"Completed.", "Runtime Error"} and not self.authority.permits_read(identity):
                    return self._attention(attempt, "completed_read_not_authorized")
                try:
                    decision = self.controller.next_action(attempt, now=self.clock(), discovered_project_ids=state["project_ids"])
                except Exception:
                    return self._attention(attempt, "watch_registration_failed")
                if decision["should_execute"] is not True:
                    return _status(attempt, decision["action"])
                request = decision["tool_request"]
                if not self._request_valid(request, identity):
                    raise ValueError("controller_request_not_whitelisted")
            self._bind(attempt, identity)
            stamp = self.clock()
            if type(stamp) is not datetime or stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("aware_host_clock_required")
            correlation = uuid4().hex
            self._append(attempt, dict(request, kind="reserved", correlation_id=correlation,
                                      reserved_at=stamp.astimezone(timezone.utc).isoformat(), decision_hash=content_hash(decision)))
            return dict(request, schema_version=1, type="tool_request", attempt_id=attempt, correlation_id=correlation)

    def accept_response(self, message):
        """Consume only the exact reserved response; never persist native raw."""
        attempt = _attempt(message.get("attempt_id")) if type(message) is dict else _attempt(None)
        if not self.enabled:
            return _status(attempt, "dispatch_disabled")
        encoded = canonical_json(message)
        if len(encoded) > MAX_LINE:
            return _status(attempt, "attention_required", "response_too_large")
        response_hash = sha256(encoded).hexdigest()
        with self.store.locked(self.LOCK):
            current = self.controller.status(attempt)
            identity = self._identity(current)
            state = self._load(attempt, identity)
            # Unsolicited observations cannot enroll an old terminal attempt.
            if not self.store.exists(self._stream(attempt)):
                return _status(attempt, "attention_required", "response_binding_rejected")
            correlation = message.get("correlation_id")
            request = state["requests"].get(correlation) if type(correlation) is str else None
            if (set(message) != {"command", "attempt_id", "correlation_id", "tool_name", "arguments", "result"}
                    or message.get("command") != "response" or request is None
                    or canonical_json(request) != canonical_json({key: message.get(key) for key in ("tool_name", "arguments")})):
                return self._attention(attempt, "response_binding_rejected", response_hash)
            previous = state["responses"].get(correlation)
            if previous:
                if previous["response_hash"] != response_hash:
                    return self._attention(attempt, "response_conflict", response_hash)
                return _status(attempt, previous["outcome"])
            envelope = dict(request, result=message["result"])
            ids = ()
            try:
                if request["tool_name"] == PROJECTS:
                    ids = project_ids(envelope)
                    if identity["project_id"] not in ids:
                        return self._attention(attempt, "project_not_discovered", response_hash)
                    outcome = "projects_observed"
                elif request["tool_name"] == HISTORY:
                    self.controller.record_history(attempt, envelope)
                    outcome = "history_observed"
                else:
                    native = _native(envelope["result"], allow_tool_error=True)
                    if (type(native) is not dict or type(native.get("success")) is not bool
                            or set(native) - {"success", "errors", "backtest"}):
                        raise ValueError("invalid_native_read")
                    if native["success"]:
                        backtest = native.get("backtest")
                        if (native.get("errors") or type(backtest) is not dict
                                or type(backtest.get("projectId")) is not int
                                or backtest["projectId"] != identity["project_id"]
                                or backtest.get("backtestId") != identity["backtest_id"]
                                or type(backtest.get("completed")) is not bool
                                or backtest.get("status") not in {"Completed.", "Runtime Error"}
                                or type(backtest.get("progress")) not in {int, float}
                                or not math.isfinite(backtest["progress"]) or not 0 <= backtest["progress"] <= 1
                                or (backtest["status"] == "Completed." and (backtest["completed"] is not True or backtest["progress"] != 1))):
                            raise ValueError("invalid_native_read")
                    elif (set(native) != {"success", "errors"}
                          or envelope["result"].get("isError") is not True
                          or type(native["errors"]) is not list or len(native["errors"]) < 2
                          or native["errors"][0] != "The backtest ended with a runtime error."
                          or any(type(e) is not str or not e.strip() for e in native["errors"][1:])):
                        raise ValueError("invalid_native_read")
                    outcome = "awaiting_native_receipt"
            except Exception:
                return self._attention(attempt, "invalid_native_response", response_hash)
            self._append(attempt, {"kind": "response", "correlation_id": correlation,
                                  "response_hash": response_hash, "outcome": outcome, "project_ids": list(ids)})
            return _status(attempt, outcome)

    def command(self, message):
        if type(message) is not dict:
            raise ValueError("invalid_message")
        if message.get("command") == "response":
            return self.accept_response(message)
        if set(message) != {"command", "attempt_id"}:
            raise ValueError("invalid_message")
        command, attempt = message["command"], _attempt(message["attempt_id"])
        if command not in {"wake", "register", "sync", "status"}:
            raise ValueError("invalid_command")
        if not self.enabled:
            return _status(attempt, "dispatch_disabled")
        if command == "wake":
            return self.prepare(attempt)
        if command == "status":
            return self.inspect(attempt)
        try:
            result = getattr(self.controller, command)(attempt)
        except Exception:
            return _status(attempt, "attention_required", "watch_registration_failed")
        return _status(attempt, result["action"])

    def run_once(self, attempt, client):
        """Inject client.call_tool(name, arguments); native output stays in memory.

        A client exception (including response loss) consumes the reservation.
        Do not retry. A later original response may be fed to accept_response.
        """
        request = self.prepare(attempt)
        if request["type"] != "tool_request":
            return request
        try:
            result = client.call_tool(request["tool_name"], dict(request["arguments"]))
        except Exception:
            return _status(attempt, "attention_required", "reserved_response_unknown")
        return self.accept_response({key: request[key] for key in ("attempt_id", "correlation_id", "tool_name", "arguments")} |
                                    {"command": "response", "result": result})


def serve(host, input_stream, output_stream):
    while True:
        line = input_stream.readline(MAX_LINE + 1)
        if not line:
            return
        try:
            if len(line.encode("utf-8")) > MAX_LINE or not line.endswith("\n"):
                raise ValueError("invalid_line")
            result = host.command(strict_json(line))
        except Exception:
            # Error details and arbitrary third-party content never reach stdout.
            result = _status(None, "attention_required", "invalid_message_or_store_state")
        output_stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
        output_stream.flush()
        if len(line) > MAX_LINE:
            return  # Never parse the unconsumed tail as a second message.


def main(argv=None, *, input_stream=None, output_stream=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "serve"))
    parser.add_argument("--attempt")
    parser.add_argument("--enable-dispatch", action="store_true")
    parser.add_argument("--host-factory", help="Trusted installed Python module:function; never stdin authority")
    args = parser.parse_args(argv)
    if args.command == "plan" and not args.attempt:
        parser.error("plan requires --attempt")
    if args.enable_dispatch and not args.host_factory:
        parser.error("dispatch requires a trusted --host-factory")
    host = FollowupHost()
    if args.enable_dispatch:
        module, separator, name = args.host_factory.partition(":")
        if not separator or not module or not name.isidentifier():
            parser.error("host factory must be module:function")
        host = getattr(importlib.import_module(module), name)()
        if type(host) is not FollowupHost or not host.enabled:
            parser.error("factory must return an explicitly enabled FollowupHost")
        host.clock = utc_now  # Production CLI cannot inherit a factory's test clock.
    output_stream = sys.stdout if output_stream is None else output_stream
    if args.command == "serve":
        serve(host, sys.stdin if input_stream is None else input_stream, output_stream)
    else:
        output_stream.write(json.dumps(host.command({"command": "status", "attempt_id": args.attempt})) + "\n")
        output_stream.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
