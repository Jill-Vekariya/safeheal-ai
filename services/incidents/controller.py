"""Transactional SQLite incident lifecycle and evidence-grounded deterministic diagnosis."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4

from services.incidents.rules import HOLDS, MAX_GAP, RECOVERY_HOLD, RULE_VERSION, evaluate


def utc(value):
    return None if value is None else datetime.fromtimestamp(value, timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Controller:
    def __init__(self, database):
        if str(database) != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(database), timeout=5, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        if self.db.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
            self.db.close()
            raise ValueError("Unsupported incident database schema")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY, at REAL NOT NULL UNIQUE, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, service TEXT NOT NULL, rule TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('pending','open','recovering','resolved')),
                detected_at REAL NOT NULL, opened_at REAL, updated_at REAL NOT NULL,
                resolved_at REAL, alert_since REAL, recovery_since REAL,
                last_sample_at REAL NOT NULL, last_evidence_id INTEGER NOT NULL REFERENCES evidence(id),
                resolution TEXT, version TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS active_fingerprint ON incidents(service,rule)
                WHERE state != 'resolved';
            CREATE TABLE IF NOT EXISTS transitions (
                id INTEGER PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id),
                at REAL NOT NULL, previous TEXT, state TEXT NOT NULL, reason TEXT NOT NULL,
                evidence_id INTEGER NOT NULL REFERENCES evidence(id));
            CREATE TABLE IF NOT EXISTS evaluations (
                evidence_id INTEGER NOT NULL REFERENCES evidence(id), service TEXT NOT NULL,
                rule TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL, value REAL,
                PRIMARY KEY(evidence_id,service,rule));
            CREATE TABLE IF NOT EXISTS diagnoses (
                incident_id TEXT NOT NULL REFERENCES incidents(id), evidence_id INTEGER NOT NULL REFERENCES evidence(id),
                document TEXT NOT NULL, PRIMARY KEY(incident_id,evidence_id));
            CREATE TABLE IF NOT EXISTS correlations (
                root_id TEXT NOT NULL REFERENCES incidents(id), related_id TEXT NOT NULL REFERENCES incidents(id),
                evidence_id INTEGER NOT NULL REFERENCES evidence(id), relation TEXT NOT NULL,
                PRIMARY KEY(root_id,related_id,evidence_id));
            PRAGMA user_version=1;
        """)

    def close(self):
        with self.lock:
            self.db.close()

    def ingest(self, snapshot):
        document = encoded({"rule_version": RULE_VERSION, **snapshot.document()})
        if not math.isfinite(snapshot.at) or snapshot.at < 0 or len(document.encode()) > 4_000_000:
            raise ValueError("Invalid or oversized evidence")
        verdicts = evaluate(snapshot)
        with self.lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                latest = self.db.execute("SELECT id,at,document FROM evidence ORDER BY at DESC LIMIT 1").fetchone()
                if latest and snapshot.at <= latest["at"]:
                    if snapshot.at == latest["at"] and document == latest["document"]:
                        self.db.rollback()
                        return latest["id"]
                    raise ValueError("Out-of-order or conflicting evidence")
                gap = latest is not None and snapshot.at - latest["at"] > MAX_GAP
                eid = self.db.execute("INSERT INTO evidence(at,document) VALUES (?,?)", (snapshot.at, document)).lastrowid
                for verdict in verdicts:
                    self.db.execute("INSERT INTO evaluations VALUES (?,?,?,?,?,?)",
                                    (eid, verdict.service, verdict.rule, verdict.decision, verdict.reason, verdict.value))
                    self._advance(verdict, snapshot.at, eid, gap)
                self._diagnose(snapshot.at, eid, verdicts)
                self.db.commit()
                return eid
            except BaseException:
                self.db.rollback()
                raise

    def _transition(self, incident, state, at, eid, reason):
        previous = incident["state"]
        if previous == state:
            return
        self.db.execute("INSERT INTO transitions(incident_id,at,previous,state,reason,evidence_id) VALUES (?,?,?,?,?,?)",
                        (incident["id"], at, previous, state, reason, eid))
        incident["state"] = state

    def _advance(self, v, at, eid, gap):
        row = self.db.execute("SELECT * FROM incidents WHERE service=? AND rule=? AND state!='resolved'",
                              (v.service, v.rule)).fetchone()
        if row is None:
            if v.decision != "alert":
                return
            iid = str(uuid4())
            self.db.execute("""INSERT INTO incidents
                (id,service,rule,state,detected_at,updated_at,alert_since,last_sample_at,last_evidence_id,version)
                VALUES (?,?,?,'pending',?,?,?,?,?,?)""",
                (iid, v.service, v.rule, at, at, v.sample_at, v.sample_at, eid, RULE_VERSION))
            self.db.execute("INSERT INTO transitions(incident_id,at,state,reason,evidence_id) VALUES (?,?,'pending',?,?)",
                            (iid, at, "first qualifying observation", eid))
            return
        incident = dict(row)
        if gap:
            incident["alert_since"] = incident["recovery_since"] = None
            if incident["state"] == "recovering":
                self._transition(incident, "open", at, eid, "collection gap broke recovery window")
        if v.sample_at <= incident["last_sample_at"] and v.decision != "unknown":
            # Replaying the same scrape cannot mature pending or recovery timers.
            if gap:
                self.db.execute("UPDATE incidents SET state=?,alert_since=NULL,recovery_since=NULL WHERE id=?",
                                (incident["state"], incident["id"]))
            return
        incident["last_sample_at"] = max(v.sample_at, incident["last_sample_at"])
        if v.decision == "alert":
            if incident["state"] == "pending":
                if incident["alert_since"] is None:
                    incident["alert_since"] = v.sample_at
                if v.sample_at - incident["alert_since"] >= HOLDS[v.rule]:
                    self._transition(incident, "open", at, eid, "continuous qualifying failure window")
                    incident["opened_at"] = at
            elif incident["state"] == "recovering":
                self._transition(incident, "open", at, eid, "failure recurred")
            incident["recovery_since"] = None
        elif v.decision == "clear":
            if incident["state"] == "pending":
                self._transition(incident, "resolved", at, eid, "transient condition cleared before opening")
                incident["resolution"] = "transient"
            elif incident["state"] == "open":
                self._transition(incident, "recovering", at, eid, "first qualifying recovery observation")
                incident["recovery_since"] = v.sample_at
            elif v.sample_at - incident["recovery_since"] >= RECOVERY_HOLD:
                self._transition(incident, "resolved", at, eid, "continuous healthy recovery window")
                incident["resolution"] = "recovered"
        else:
            # Unknown/low traffic or hysteresis is never continuous failure/recovery evidence.
            incident["alert_since"] = incident["recovery_since"] = None
            if incident["state"] == "recovering":
                self._transition(incident, "open", at, eid, f"{v.decision} broke recovery window")
        if incident["state"] == "resolved":
            incident["resolved_at"] = at
        incident["updated_at"], incident["last_evidence_id"] = at, eid
        self.db.execute("""UPDATE incidents SET state=:state, opened_at=:opened_at, updated_at=:updated_at,
            resolved_at=:resolved_at, alert_since=:alert_since, recovery_since=:recovery_since,
            last_sample_at=:last_sample_at, last_evidence_id=:last_evidence_id, resolution=:resolution WHERE id=:id""", incident)

    def _diagnose(self, at, eid, verdicts):
        active = [dict(r) for r in self.db.execute("""SELECT * FROM incidents
            WHERE state IN ('open','recovering') OR
            (state='resolved' AND opened_at IS NOT NULL AND last_evidence_id=?)""", (eid,))]
        decisions = {(v.service, v.rule): v.decision for v in verdicts}
        topology = {"gateway": ("order", "payment"), "order": ("payment",), "payment": ()}
        for incident in active:
            rule, service = incident["rule"], incident["service"]
            cause = {
                "telemetry_unavailable": "insufficient_telemetry",
                "scrape_unavailable": "service_or_metrics_endpoint_unavailable",
                "high_error_rate": "server_error_spike",
                "high_latency": "request_latency_degradation",
            }[rule]
            root = None
            if rule == "high_error_rate" and decisions[(service, rule)] == "alert":
                candidates = [r for r in active if r["rule"] == "scrape_unavailable" and
                              r["service"] in topology[service] and decisions[(r["service"], r["rule"])] == "alert" and
                              abs(r["detected_at"] - incident["detected_at"]) <= 60]
                if candidates:
                    root = max(candidates, key=lambda r: topology[service].index(r["service"]))
                    cause = "suspected_dependency_unavailable"
                    self.db.execute("INSERT INTO correlations VALUES (?,?,?,'suspected_dependency')",
                                    (root["id"], incident["id"], eid))
            diagnosis = {
                "controller": "deterministic", "rule_version": RULE_VERSION, "at": utc(at),
                "classification": cause, "service": service, "suspected_root_service": root["service"] if root else None,
                "evidence_refs": [{"evidence_id": eid, "service": service, "rule": rule}] +
                                 ([{"evidence_id": eid, "service": root["service"], "rule": root["rule"]}] if root else []),
                "current_decision": decisions[(service, rule)],
                "limitations": "Symptoms and topology support hypotheses; process crash/root cause is not proven. No recovery executed.",
                "recommended_action": "inspect bounded read-only service/metrics evidence",
            }
            if decisions[(service, rule)] == "unknown":
                diagnosis["classification"] = "insufficient_current_evidence"
            if incident["state"] == "resolved":
                diagnosis["classification"] = "recovered"
            self.db.execute("INSERT INTO diagnoses VALUES (?,?,?)", (incident["id"], eid, encoded(diagnosis)))

    def list_incidents(self, limit=100, active_only=False):
        if not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        with self.lock:
            where = "WHERE state != 'resolved'" if active_only else ""
            rows = self.db.execute(f"SELECT * FROM incidents {where} ORDER BY detected_at DESC,id LIMIT ?", (limit,)).fetchall()
            return [self._public(dict(row)) for row in rows]

    def _public(self, item):
        for key in ("detected_at", "opened_at", "updated_at", "resolved_at", "alert_since", "recovery_since", "last_sample_at"):
            item[key] = utc(item[key])
        return item

    def detail(self, iid):
        with self.lock:
            row = self.db.execute("SELECT * FROM incidents WHERE id=?", (iid,)).fetchone()
            if row is None:
                return None
            result = self._public(dict(row))
            result["transitions"] = [dict(r) for r in self.db.execute(
                "SELECT * FROM transitions WHERE incident_id=? ORDER BY id DESC LIMIT 100", (iid,))]
            diagnosis = self.db.execute("SELECT document FROM diagnoses WHERE incident_id=? ORDER BY evidence_id DESC LIMIT 1", (iid,)).fetchone()
            result["diagnosis"] = json.loads(diagnosis[0]) if diagnosis else None
            result["correlations"] = [dict(r) for r in self.db.execute(
                "SELECT * FROM correlations WHERE related_id=? OR root_id=? ORDER BY evidence_id DESC LIMIT 100", (iid, iid))]
            return result

    def evidence(self, eid):
        with self.lock:
            row = self.db.execute("SELECT document FROM evidence WHERE id=?", (eid,)).fetchone()
            return json.loads(row[0]) if row else None
