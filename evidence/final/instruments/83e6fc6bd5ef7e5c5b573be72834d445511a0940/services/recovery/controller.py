"""One bounded action; proposals are data, never executable authority.

The operator owns configuration, enrollment, approvals and the audit database.
Only this controller receives the short-lived, scale-only Kubernetes credential.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from types import MappingProxyType


NAMESPACE = "safeheal-dev"
TARGET = "payment"
ACTION = "restore_payment_replica"
CATALOG = MappingProxyType({ACTION: MappingProxyType({
    "namespace": NAMESPACE, "deployment": TARGET, "from_replicas": 0,
    "to_replicas": 1, "verification": "three_consecutive_deployment_ready_observations",
})})
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}\Z")


class Denied(RuntimeError):
    """Safe, fixed error code. Never include raw proposals or API responses."""


def require(ok, code):
    if not ok:
        raise Denied(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def parse_request(value):
    require(isinstance(value, dict) and set(value) == {
        "schema_version", "request_id", "incident_id", "action"}, "invalid_schema")
    require(value["schema_version"] == "day7-recovery-v1", "invalid_version")
    require(isinstance(value["action"], str) and value["action"] in CATALOG, "action_not_allowlisted")
    for key in ("request_id", "incident_id"):
        require(isinstance(value[key], str) and _ID.fullmatch(value[key]), "invalid_identifier")
    return deepcopy(value)


def template_digest(deployment):
    spec = deepcopy(deployment["spec"])
    spec.pop("replicas", None)
    return digest(spec)


def identity(deployment, enrollment):
    m = deployment.get("metadata", {})
    require(deployment.get("kind") == "Deployment" and deployment.get("apiVersion") == "apps/v1",
            "invalid_deployment")
    require(m.get("namespace") == NAMESPACE and m.get("name") == TARGET and
            m.get("uid") == enrollment["deployment_uid"] and not m.get("deletionTimestamp"),
            "target_identity_changed")
    labels = m.get("labels", {})
    require(labels.get("app.kubernetes.io/name") == TARGET and
            labels.get("app.kubernetes.io/part-of") == "safeheal-ai", "foreign_target")
    require(template_digest(deployment) == enrollment["template_sha256"], "deployment_spec_changed")
    require(type(m.get("generation")) is int and isinstance(m.get("resourceVersion"), str),
            "invalid_target_version")
    return digest({"uid": m["uid"], "generation": m["generation"],
                   "spec": deployment["spec"]})


class Journal:
    """Durable claim-before-write, single-flight, approvals, and hash-chained audit.

    Hash chaining detects accidental corruption. A privileged filesystem attacker
    can rewrite this database; this is not an external tamper-proof log service.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY, body TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
              BEGIN SELECT RAISE(ABORT, 'append only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
              BEGIN SELECT RAISE(ABORT, 'append only'); END;
            CREATE TABLE IF NOT EXISTS approvals (
              request_id TEXT PRIMARY KEY, request_hash TEXT, fingerprint TEXT, expires REAL, used INTEGER);
            CREATE TABLE IF NOT EXISTS runs (
              request_id TEXT PRIMARY KEY, at REAL, state TEXT);
        """)

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.verify()
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def verify(self):
        previous = "0" * 64
        for seq, body, prior, hash_ in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            require(prior == previous and hash_ == digest({"seq": seq, "body": body, "previous": prior}),
                    "audit_integrity_failure")
            previous = hash_

    def event(self, at, request_hash, stage, code, **details):
        last = self.db.execute("SELECT seq,hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        seq, previous = (last[0] + 1, last[1]) if last else (1, "0" * 64)
        body = encoded({"at": at, "request_hash": request_hash, "stage": stage,
                        "code": code, **details})
        self.db.execute("INSERT INTO audit VALUES (?,?,?,?)", (
            seq, body, previous, digest({"seq": seq, "body": body, "previous": previous})))

    def close(self):
        self.db.close()


class Controller:
    def __init__(self, api, journal, enrollment, *, autonomous_enabled=False,
                 clock=time.time, monotonic=time.monotonic, sleep=time.sleep,
                 verification_seconds=120):
        require(type(autonomous_enabled) is bool, "invalid_autonomous_setting")
        require(type(verification_seconds) is int and 1 <= verification_seconds <= 120,
                "invalid_verification_deadline")
        self.api, self.journal, self.enrollment = api, journal, deepcopy(enrollment)
        self.autonomous_enabled = autonomous_enabled
        self.clock, self.monotonic, self.sleep = clock, monotonic, sleep
        self.verification_seconds = verification_seconds

    def _snapshot(self):
        d = self.api.deployment()
        fingerprint = identity(d, self.enrollment)
        require(type(d["spec"].get("replicas")) is int and d["spec"]["replicas"] == 0,
                "live_precondition_not_zero")
        return d, fingerprint

    def _consistent_snapshot(self):
        # Deployment status may advance between the two GETs. Bounded read-only
        # resampling is safe; UID/spec/replica mismatches still fail immediately.
        # This never retries a write or changes the enrolled target.
        for attempt in range(3):
            d, fingerprint = self._snapshot()
            scale = self.api.scale()
            m = scale.get("metadata", {})
            spec = scale.get("spec")
            require(m.get("uid") == d["metadata"]["uid"] and m.get("name") == TARGET and
                    m.get("namespace") == NAMESPACE and isinstance(m.get("resourceVersion"), str) and
                    isinstance(spec, dict) and set(spec) <= {"replicas"} and
                    type(spec.get("replicas", 0)) is int and spec.get("replicas", 0) == 0,
                    "scale_precondition_changed")
            if m["resourceVersion"] == d["metadata"]["resourceVersion"]:
                return d, fingerprint, scale
            if attempt < 2:
                self.sleep(.1)
        raise Denied("scale_precondition_changed")

    def approve(self, raw):
        """Operator-only entry point; never offered to the model transport."""
        try:
            return self._approve(raw)
        except Exception as exc:
            code = str(exc) if isinstance(exc, Denied) else "approval_error"
            with self.journal.transaction():
                self.journal.event(self.clock(), digest(raw), "approval_denial", code)
            raise Denied(code) from None

    def _approve(self, raw):
        request = parse_request(raw)
        request_hash = digest(request)
        _, fingerprint = self._snapshot()
        with self.journal.transaction():
            require(not self.journal.db.execute("SELECT 1 FROM runs WHERE request_id=?",
                    (request["request_id"],)).fetchone(), "request_already_claimed")
            self.journal.db.execute("INSERT INTO approvals VALUES (?,?,?,?,0)",
                (request["request_id"], request_hash, fingerprint, self.clock() + 180))
            self.journal.event(self.clock(), request_hash, "approval", "operator_approved",
                               fingerprint=fingerprint, expires=self.clock() + 180)
        return {"status": "approved", "request_hash": request_hash, "expires_in_seconds": 180}

    def run(self, raw, *, mode="dry-run"):
        # Never retain untrusted text in errors or audit. CLI bounds raw bytes first.
        request_hash = digest(raw)
        claimed = False
        try:
            request = parse_request(raw)
            require(mode in ("dry-run", "approval", "autonomous"), "invalid_mode")
            require(mode != "autonomous" or self.autonomous_enabled, "autonomous_disabled")
            d, fingerprint, scale = self._consistent_snapshot()
            m = scale.get("metadata", {})
            patch = [{"op": "test", "path": "/metadata/uid", "value": m["uid"]},
                     {"op": "test", "path": "/metadata/resourceVersion", "value": m["resourceVersion"]},
                     # ScaleSpec omits a zero replicas field in real API JSON.
                     # Test the complete spec, then add/replace exactly this field.
                     {"op": "test", "path": "/spec", "value": scale["spec"]},
                     {"op": "add", "path": "/spec/replicas", "value": 1}]
            with self.journal.transaction():
                db = self.journal.db
                require(not db.execute("SELECT 1 FROM runs WHERE state IN ('running','uncertain')").fetchone(),
                        "unresolved_execution")
                require(not db.execute("SELECT 1 FROM runs WHERE request_id=?", (request["request_id"],)).fetchone(),
                        "request_already_claimed")
                last = db.execute("SELECT MAX(at),COUNT(*) FROM runs WHERE at>?", (self.clock()-3600,)).fetchone()
                require(last[1] < 3 and (last[0] is None or 300 <= self.clock()-last[0]), "recovery_rate_limited")
                if mode == "approval":
                    approval = db.execute("SELECT request_hash,fingerprint,expires,used FROM approvals WHERE request_id=?",
                                          (request["request_id"],)).fetchone()
                    require(approval is not None and approval[0] == request_hash and approval[1] == fingerprint
                            and self.clock() < approval[2] and approval[3] == 0, "approval_missing_stale_or_used")
                    db.execute("UPDATE approvals SET used=1 WHERE request_id=?", (request["request_id"],))
                self.journal.event(self.clock(), request_hash, "policy", "permitted", mode=mode,
                                   action=ACTION, target=TARGET, fingerprint=fingerprint, patch=patch)
                if mode != "dry-run":
                    db.execute("INSERT INTO runs VALUES (?,?,?)", (request["request_id"], self.clock(), "running"))
                    self.journal.event(self.clock(), request_hash, "execution", "intent_durably_recorded")
            if mode == "dry-run":
                return {"status": "dry_run", "execution_allowed": False, "catalog": dict(CATALOG[ACTION]),
                        "request_hash": request_hash, "patch": patch}
            claimed = True
            # Exactly one conditional write. A timeout may mean applied; NEVER retry.
            self.api.restore(patch)
            with self.journal.transaction():
                self.journal.event(self.clock(), request_hash, "execution", "api_acknowledged")
            observations = self._verify(d["metadata"]["generation"] + 1)
            with self.journal.transaction():
                self.journal.db.execute("UPDATE runs SET state='verified' WHERE request_id=?", (request["request_id"],))
                self.journal.event(self.clock(), request_hash, "verification", "recovery_verified",
                                   observations=observations)
            return {"status": "verified", "request_hash": request_hash, "action": ACTION,
                    "observations": observations, "verification": CATALOG[ACTION]["verification"]}
        except Exception as exc:
            code = str(exc) if isinstance(exc, Denied) else "controller_error"
            # Failure to write audit propagates: no success result or further action.
            with self.journal.transaction():
                if claimed:
                    self.journal.db.execute("UPDATE runs SET state='uncertain' WHERE request_id=?",
                                            (request["request_id"],))
                self.journal.event(self.clock(), request_hash, "failure" if claimed else "denial", code)
            raise Denied(code) from None

    def _verify(self, minimum_generation):
        deadline = self.monotonic() + self.verification_seconds
        observations, consecutive = [], 0
        while self.monotonic() < deadline:
            d = self.api.deployment()
            identity(d, self.enrollment)
            require(d["spec"].get("replicas") == 1, "verification_replicas_changed")
            s = d.get("status", {})
            require(d["metadata"]["generation"] == minimum_generation, "verification_generation_changed")
            ready = (d["metadata"]["generation"] == minimum_generation and
                     s.get("observedGeneration", 0) >= d["metadata"]["generation"] and
                     all(s.get(k, 0) == 1 for k in ("updatedReplicas", "readyReplicas", "availableReplicas", "replicas"))
                     and s.get("unavailableReplicas", 0) == 0)
            observations.append({"at": self.clock(), "generation": d["metadata"]["generation"],
                                 "observed_generation": s.get("observedGeneration"), "ready": ready})
            consecutive = consecutive + 1 if ready else 0
            if consecutive == 3:
                return observations
            self.sleep(min(1, max(0, deadline-self.monotonic())))
        raise Denied("verification_timeout")
