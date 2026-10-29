"""Bounded metadata follow-up of one already accepted engineering LEAN job.

This module never calls a connector, claims an execution or settles a result.
The trusted dispatcher supplies its UTC clock and actual list_projects IDs.
After a grace period, at most one bounded historical-directory reconciliation
is reserved durably. A crash/unknown response is attention, never a retry or a
failed backtest. Only the existing Registry can establish a terminal result.
"""
from datetime import datetime, timedelta, timezone
import json
import math
import re

from .artifacts import canonical_json, content_hash, decode_events
from .engineering_receipts import _native
from .engineering_tasks import EngineeringTaskBridge, EngineeringTaskPlan


class TaskFollowupError(ValueError):
    """A follow-up request or native observation is not admissible."""


_POLICY = {"schema_version": 1, "notification_grace_seconds": 1800, "max_history_pages": 3}
_TERMINAL = {"completed", "failed"}
_PLATFORM_TERMINAL = {"Completed.", "Runtime Error"}
_PLATFORM_STATES = _PLATFORM_TERMINAL | {"In Queue...", "In Progress..."}
_SUMMARY_FIELDS = {"alpha", "backtestId", "beta", "compoundingAnnualReturn", "created", "drawdown",
    "lossRate", "name", "netProfit", "optimizationId", "parameterSet", "parameters", "progress",
    "psr", "sharpeRatio", "snapshotId", "sortinoRatio", "status", "tags", "tradeableDates",
    "trades", "treynorRatio", "winRate"}
_NUMERIC_FIELDS = {"alpha", "beta", "compoundingAnnualReturn", "drawdown", "lossRate", "netProfit",
    "psr", "sharpeRatio", "sortinoRatio", "trades", "treynorRatio", "winRate"}


def _fail(message):
    raise TaskFollowupError(message) from None


def validate_policy(raw):
    """Validate the explicit fixed follow-up policy without store or clock I/O."""
    if (type(raw) is not dict or set(raw) != set(_POLICY)
            or any(type(raw[key]) is not int or raw[key] != value for key, value in _POLICY.items())):
        _fail("An explicit supported bounded follow-up policy is required")
    return json.loads(canonical_json(raw))


def _clock(value):
    if type(value) is str:
        if not value or len(value) > 128:
            _fail("A bounded aware clock is required")
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            _fail("A bounded aware clock is required")
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        _fail("A timezone-aware operator clock is required")
    return value.astimezone(timezone.utc)


def _text(value, maximum=256):
    return type(value) is str and bool(value.strip()) and len(value) <= maximum and not any(c in value for c in "\r\n\x00")


class TaskFollowupController:
    """One watch stream per accepted attempt, using the existing Registry lock.

    Call these methods after the submission transaction returns. This is not a
    second budget registry and must not be invoked while holding Registry.LOCK.
    The stream contains identities, status/counts and observation hashes only.
    """
    def __init__(self, registry, policy):
        self.policy = validate_policy(policy)
        self.registry, self.store = registry, registry.store

    @staticmethod
    def _stream(attempt):
        if type(attempt) is not str or re.fullmatch("[0-9a-f]{32}", attempt) is None:
            _fail("A canonical existing attempt ID is required")
        return "engineering/followup/" + attempt + "/events.jsonl"

    def _context(self, state, attempt):
        self._stream(attempt)
        record = state["attempts"].get(attempt)
        if record is None or record["stage"] != "lean":
            _fail("Follow-up requires an existing LEAN attempt")
        encoded = self.store.read_bytes("configurations/" + record["config_id"] + ".json")
        package = json.loads(encoded)
        if (type(package) is not dict or canonical_json(package) != encoded or content_hash(package) != record["config_id"]
                or set(package) != {"engineering_task_schema_version", "plan"}
                or type(package["engineering_task_schema_version"]) is not int
                or package["engineering_task_schema_version"] != 1
                or type(package["plan"]) is not dict
                or package["plan"].get("task_kind") == "historical_collection"):
            _fail("Follow-up requires the original Engineering configuration")
        document = package["plan"]
        plan = EngineeringTaskPlan.from_dict(document, discovered_project_ids=(document["project_id"],))
        bridge = EngineeringTaskBridge(self.registry, plan)
        if bridge.config_id != record["config_id"] or record["operation_key"] != bridge._operation("lean"):
            _fail("Attempt does not match the original frozen Engineering operation")
        identity = {"plan_hash": plan.hash, "config_id": record["config_id"], "attempt_id": attempt,
            "stage": "lean", "project_id": document["project_id"],
            "source_manifest_hash": document["source_manifest_hash"],
            "deployment_hash": document["deployment_hash"], "data_request_hash": plan.request_hash}
        submitted = bridge._recorded_submission({"identity": identity, "external_identity_kind": "quantconnect_backtest_id"})
        if record.get("external_id") != submitted["external_id"] or record["status"] not in {"pending", "ambiguous", "completed", "failed"}:
            _fail("Follow-up requires a journaled accepted submission")
        pending = [event["event"] for event in decode_events(self.store.read_bytes(self.registry.JOURNAL))
                   if event["event"].get("kind") == "pending" and event["event"].get("attempt_id") == attempt
                   and event["event"].get("external_id") == submitted["external_id"]]
        if not pending:
            _fail("The original accepted-submission clock is unavailable")
        start = min(_clock(event["recorded_at"]) for event in pending)
        return {"identity": identity, "backtest_id": submitted["external_id"],
                "submitted_at": start.isoformat(),
                "deadline": (start + timedelta(seconds=self.policy["notification_grace_seconds"])).isoformat()}, record

    def _load(self, context, record_status):
        key = self._stream(context["identity"]["attempt_id"])
        state = {"registered": False, "reserved_pages": [], "observed_pages": {}, "read_reserved": False, "finished": False, "last_reserved_at": None}
        if not self.store.exists(key):
            return state
        for item in decode_events(self.store.read_bytes(key)):
            event = item["event"]
            kind = event.get("kind")
            if state["finished"]:
                _fail("A finished follow-up cannot acquire further events")
            if kind == "registered":
                if state["registered"] or set(event) != {"kind", "context", "policy"} or canonical_json(event["context"]) != canonical_json(context) or canonical_json(event["policy"]) != canonical_json(self.policy):
                    _fail("Frozen follow-up identity or policy changed")
                state["registered"] = True
            elif kind == "history_reserved":
                if (not state["registered"] or set(event) != {"kind", "page", "reserved_at"}
                        or type(event["page"]) is not int or event["page"] != len(state["reserved_pages"]) + 1
                        or event["page"] > self.policy["max_history_pages"]
                        or state["read_reserved"]
                        or (state["reserved_pages"] and (state["reserved_pages"][-1] not in state["observed_pages"]
                            or not self._latest(state)["success"] or self._latest(state)["target"] is not None
                            or self._latest(state)["total_pages"] is None
                            or state["reserved_pages"][-1] >= self._latest(state)["total_pages"]))):
                    _fail("Invalid historical-request reservation")
                self._reservation_clock(event, context, state)
                state["reserved_pages"].append(event["page"])
            elif kind == "history_observed":
                if (not state["registered"] or set(event) != {"kind", "page", "observation"}
                        or type(event["page"]) is not int
                        or event["page"] not in state["reserved_pages"] or event["page"] in state["observed_pages"]):
                    _fail("Historical observation has no unique reserved request")
                self._validate_observation(event["observation"])
                if event["observation"]["target"] is not None and event["observation"]["target"]["backtest_id"] != context["backtest_id"]:
                    _fail("Historical target differs from the accepted backtest")
                state["observed_pages"][event["page"]] = event["observation"]
            elif kind == "completed_read_reserved":
                if (set(event) != {"kind", "reserved_at"} or state["read_reserved"]
                        or not self._latest(state).get("target")
                        or self._latest(state)["target"]["status"] not in _PLATFORM_TERMINAL):
                    _fail("Completed-read reservation lacks native terminal evidence")
                self._reservation_clock(event, context, state)
                state["read_reserved"] = True
            elif kind == "registry_finished":
                if (set(event) != {"kind", "registry_status"} or not state["registered"]
                        or event["registry_status"] not in _TERMINAL
                        or event["registry_status"] != record_status):
                    _fail("Only the actual Registry terminal state can close a watch")
                state["finished"] = True
            else:
                _fail("Unknown follow-up event")
        return state

    @staticmethod
    def _reservation_clock(event, context, state):
        raw = event.get("reserved_at")
        if type(raw) is not str:
            _fail("A reservation requires its canonical UTC operator clock")
        instant = _clock(raw)
        if (instant.isoformat() != raw or instant < _clock(context["deadline"])
                or (state["last_reserved_at"] is not None and instant < state["last_reserved_at"])):
            _fail("Reservation clock is before grace, non-UTC, or moves backwards")
        state["last_reserved_at"] = instant

    @staticmethod
    def _validate_observation(value):
        if (type(value) is not dict or set(value) != {"response_hash", "success", "total_pages", "target"}
                or type(value["response_hash"]) is not str or re.fullmatch("[0-9a-f]{64}", value["response_hash"]) is None
                or type(value["success"]) is not bool
                or (value["total_pages"] is not None and (type(value["total_pages"]) is not int or not 1 <= value["total_pages"] <= 100000))):
            _fail("Invalid closed historical observation")
        if value["target"] is not None:
            target = value["target"]
            if (type(target) is not dict or set(target) != {"backtest_id", "status", "progress"}
                    or not _text(target["backtest_id"]) or type(target["status"]) is not str
                    or target["status"] not in _PLATFORM_STATES or value["success"] is not True
                    or type(target["progress"]) not in {int, float} or not math.isfinite(target["progress"])
                    or not 0 <= target["progress"] <= 1
                    or (target["status"] == "Completed." and target["progress"] != 1)):
                _fail("Invalid bounded target status")

    @staticmethod
    def _latest(watch):
        return watch["observed_pages"].get(max(watch["observed_pages"], default=0), {})

    def _append(self, context, event):
        self.store.append_event(self._stream(context["identity"]["attempt_id"]), event)

    def _ensure(self, context, watch):
        if not watch["registered"]:
            self._append(context, {"kind": "registered", "context": context, "policy": self.policy})
            watch["registered"] = True

    @staticmethod
    def _result(context, status, action, reason, *, execute=False, request=None):
        return {"schema_version": 1, "attempt_id": context["identity"]["attempt_id"],
            "project_id": context["identity"]["project_id"], "backtest_id": context["backtest_id"],
            "status": status, "action": action, "reason": reason, "should_execute": execute,
            "tool_request": request, "submitted_at": context["submitted_at"], "deadline": context["deadline"]}

    def _finished(self, context, record):
        return self._result(context, record["status"], "finished", "Registry has a verified terminal transition")

    def register(self, attempt_id):
        with self.store.locked(self.registry.LOCK):
            context, record = self._context(self.registry._replay(), attempt_id)
            if record["status"] in _TERMINAL:
                return self._finished(context, record)
            watch = self._load(context, record["status"])
            self._ensure(context, watch)
            return self._result(context, "waiting_delivery", "wait_for_delivery", "Watch registered without connector dispatch")

    def status(self, attempt_id):
        with self.store.locked(self.registry.LOCK):
            context, record = self._context(self.registry._replay(), attempt_id)
            if record["status"] in _TERMINAL:
                return self._finished(context, record)
            watch = self._load(context, record["status"])
            if not watch["registered"]:
                return self._result(context, "unregistered", "register_watch", "No follow-up stream exists")
            if watch["reserved_pages"]:
                latest = self._latest(watch)
                page = len(watch["reserved_pages"])
                if watch["read_reserved"] or page not in watch["observed_pages"]:
                    return self._result(context, "attention_required", "attention_required", "A reserved request has no verified settlement; do not redispatch")
                if ((latest.get("target") and latest["target"]["status"] not in _PLATFORM_TERMINAL)
                        or not latest["success"] or latest["total_pages"] is None
                        or (not latest.get("target") and (page >= latest["total_pages"] or page >= self.policy["max_history_pages"]))):
                    return self._result(context, "attention_required", "attention_required", "Bounded reconciliation needs operator attention, not another polling cycle")
                return self._result(context, "reconciliation_started", "continue_reconciliation", "A bounded reconciliation is already recorded")
            return self._result(context, "waiting_delivery", "wait_for_delivery", "Awaiting delivery or grace deadline")

    def sync(self, attempt_id):
        """Read authoritative status; never fabricate a watch for old terminal work."""
        with self.store.locked(self.registry.LOCK):
            context, record = self._context(self.registry._replay(), attempt_id)
            watch = self._load(context, record["status"])
            if record["status"] in _TERMINAL:
                if watch["registered"] and not watch["finished"]:
                    self._append(context, {"kind": "registry_finished", "registry_status": record["status"]})
                return self._finished(context, record)
            return self._result(context, "waiting_delivery" if watch["registered"] else "unregistered",
                "wait_for_delivery" if watch["registered"] else "register_watch",
                "Registry is unresolved; sync does not create or close a watch")

    @staticmethod
    def _projects(context, discovered):
        if not isinstance(discovered, (tuple, list)) or any(type(value) is not int or value <= 0 for value in discovered):
            _fail("A matching actual list_projects result is required before connector dispatch")
        if not discovered:
            return False
        if context["identity"]["project_id"] not in discovered:
            _fail("The target is absent from the supplied actual list_projects result")
        return True

    def next_action(self, attempt_id, *, now, discovered_project_ids=()):
        with self.store.locked(self.registry.LOCK):
            context, record = self._context(self.registry._replay(), attempt_id)
            if record["status"] in _TERMINAL:
                return self._finished(context, record)
            instant = _clock(now)
            if instant < _clock(context["submitted_at"]):
                _fail("Operator clock precedes the accepted submission")
            watch = self._load(context, record["status"])
            if watch["last_reserved_at"] is not None and instant < watch["last_reserved_at"]:
                _fail("Operator clock moved backwards after a reserved request")
            if instant < _clock(context["deadline"]):
                self._ensure(context, watch)
                return self._result(context, "waiting_delivery", "wait_for_delivery", "Notification grace period has not elapsed")
            latest = self._latest(watch)
            if watch["read_reserved"]:
                return self._result(context, "attention_required", "attention_required", "Completed read already reserved; settle its original response, never redispatch")
            if latest.get("target"):
                if latest["target"]["status"] not in _PLATFORM_TERMINAL:
                    return self._result(context, "attention_required", "attention_required", "Historical observation is still queued or running; do not poll or resubmit")
                if not self._projects(context, discovered_project_ids):
                    return self._result(context, "project_listing_required", "list_projects", "trusted_project_listing_required")
                self._ensure(context, watch)
                self._append(context, {"kind": "completed_read_reserved", "reserved_at": instant.isoformat()})
                return self._result(context, "terminal_observed", "read_completed_backtest", "Native historical observation establishes a terminal state", execute=True,
                    request={"tool_name": "mcp__quantconnect__read_backtest", "arguments": {"projectId": context["identity"]["project_id"], "backtestId": context["backtest_id"]}})
            previous = len(watch["reserved_pages"])
            if previous and previous not in watch["observed_pages"]:
                return self._result(context, "attention_required", "attention_required", "Reserved historical request has no response; outcome unknown, never redispatch")
            if previous and (not latest["success"] or latest["total_pages"] is None):
                return self._result(context, "attention_required", "attention_required", "Historical directory unavailable or pagination unknown")
            if previous and (previous >= latest["total_pages"] or previous >= self.policy["max_history_pages"]):
                return self._result(context, "attention_required", "attention_required", "Target absent from bounded historical pages; no new task is authorized")
            if not self._projects(context, discovered_project_ids):
                return self._result(context, "project_listing_required", "list_projects", "trusted_project_listing_required")
            self._ensure(context, watch)
            page = previous + 1
            self._append(context, {"kind": "history_reserved", "page": page, "reserved_at": instant.isoformat()})
            return self._result(context, "reconciliation_reserved", "list_backtests", "One bounded historical-directory page reserved before dispatch", execute=True,
                request={"tool_name": "mcp__quantconnect__list_backtests", "arguments": {"projectId": context["identity"]["project_id"], "page": page}})

    def record_history(self, attempt_id, envelope):
        with self.store.locked(self.registry.LOCK):
            context, record = self._context(self.registry._replay(), attempt_id)
            if record["status"] in _TERMINAL:
                return self._finished(context, record)
            watch = self._load(context, record["status"])
            if (type(envelope) is not dict or set(envelope) != {"tool_name", "arguments", "result"}
                    or envelope["tool_name"] != "mcp__quantconnect__list_backtests"
                    or type(envelope["arguments"]) is not dict or set(envelope["arguments"]) != {"projectId", "page"}):
                _fail("A bound native historical-directory observation is required")
            args = envelope["arguments"]
            page = args["page"]
            if (type(page) is not int or page not in watch["reserved_pages"]
                    or type(args["projectId"]) is not int or args["projectId"] != context["identity"]["project_id"]):
                _fail("Historical response does not match its reserved page and project")
            response_hash = content_hash(envelope)
            if page in watch["observed_pages"]:
                if watch["observed_pages"][page]["response_hash"] != response_hash:
                    _fail("A reserved page cannot acquire conflicting responses")
                return self._result(context, "observed", "continue_reconciliation", "Identical historical observation already recorded")
            try:
                native = _native(envelope["result"])
            except (ValueError, TypeError):
                _fail("Native historical carriers are invalid or inconsistent")
            if (type(native) is not dict or set(native) - {"success", "errors", "backtests", "totalPages"}
                    or type(native.get("success")) is not bool):
                _fail("Unknown historical-directory output is prohibited")
            errors = native.get("errors", [])
            if type(errors) is not list or len(errors) > 32 or any(not _text(value, 4096) for value in errors):
                _fail("Invalid bounded historical error metadata")
            total = native.get("totalPages")
            if total is not None and (type(total) is not int or not 1 <= total <= 100000 or page > total):
                _fail("Invalid historical pagination")
            if watch["observed_pages"] and self._latest(watch)["total_pages"] != total:
                _fail("Historical pagination changed during one reconciliation")
            target = None
            if native["success"]:
                if errors or type(native.get("backtests")) is not list or len(native["backtests"]) > 1000:
                    _fail("Successful history requires a bounded backtest summary list")
                seen = set()
                for item in native["backtests"]:
                    self._summary(item)
                    if item["backtestId"] in seen:
                        _fail("Duplicate historical identities are ambiguous")
                    seen.add(item["backtestId"])
                    if item["backtestId"] == context["backtest_id"]:
                        target = {"backtest_id": item["backtestId"], "status": item["status"], "progress": item["progress"]}
            elif "backtests" in native and native["backtests"]:
                _fail("An unsuccessful directory cannot supply task observations")
            observation = {"response_hash": response_hash, "success": native["success"], "total_pages": total, "target": target}
            self._validate_observation(observation)
            self._append(context, {"kind": "history_observed", "page": page, "observation": observation})
            return self._result(context, "observed", "continue_reconciliation", "Historical metadata recorded; request next decision without inventing terminal completion")

    @staticmethod
    def _summary(item):
        if (type(item) is not dict or set(item) - _SUMMARY_FIELDS
                or not {"backtestId", "status", "progress"} <= set(item)
                or not _text(item["backtestId"]) or type(item["status"]) is not str
                or item["status"] not in _PLATFORM_STATES
                or type(item["progress"]) not in {int, float} or not math.isfinite(item["progress"])
                or not 0 <= item["progress"] <= 1
                or (item["status"] == "Completed." and item["progress"] != 1)):
            _fail("Invalid historical summary or terminal status")
        for key in _NUMERIC_FIELDS & set(item):
            if item[key] is not None and (type(item[key]) not in {int, float} or not math.isfinite(item[key])):
                _fail("Invalid native aggregate metadata")
        for key in {"parameters", "snapshotId", "tradeableDates"} & set(item):
            if type(item[key]) is not int or item[key] < 0:
                _fail("Invalid historical count")
        for key in {"name", "created", "optimizationId"} & set(item):
            if item[key] is not None and not _text(item[key]):
                _fail("Invalid bounded historical text")
        if "tags" in item and (type(item["tags"]) is not list or len(item["tags"]) > 32
                or any(not _text(tag) for tag in item["tags"])):
            _fail("Invalid bounded historical tags")
        if "parameterSet" in item:
            value = item["parameterSet"]
            if value != [] and (type(value) is not dict or len(value) > 32 or any(
                    not _text(k) or (type(v) is not bool and type(v) not in {str, int, float})
                    or (type(v) is str and not _text(v)) or (type(v) is float and not math.isfinite(v))
                    for k, v in value.items())):
                _fail("Unsupported native parameter metadata")
