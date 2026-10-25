"""Local incident-notification intake, not a messaging or recovery transport.

Untrusted events carry identifiers/timestamps only. A durable claim suppresses
replays before a provider request; a crash never triggers an automatic retry.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import sqlite3
import time

from services.diagnosis.evidence import encoded, timestamp, validate_bundle

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
MAX_EVENTS = 10_000
MAX_AUDIT = 50_000


def parse_event(event, now):
    if type(event) is not dict or set(event) != {"schema_version", "notification_id", "incident_id", "observed_at"}:
        raise ValueError("invalid_notification")
    if event["schema_version"] != "day8-notification-v1":
        raise ValueError("invalid_notification")
    if any(type(event[k]) is not str or not _ID.fullmatch(event[k]) for k in ("notification_id", "incident_id")):
        raise ValueError("invalid_notification")
    age = timestamp(now) - timestamp(event["observed_at"])
    if not 0 <= age <= 60:
        raise ValueError("stale_or_future_notification")
    return deepcopy(event)


class NotificationPipeline:
    def __init__(self, agent, database, *, clock=time.time):
        self.agent, self.clock = agent, clock
        path = Path(database)
        existed = path.exists() and path.stat().st_size > 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=1, isolation_level=None)
        if existed and self.db.execute("PRAGMA user_version").fetchone()[0] != 8:
            self.db.close()
            raise ValueError("Unsupported notification journal")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS inbox (
              notification_id TEXT PRIMARY KEY, event_hash TEXT, incident_id TEXT,
              evidence_hash TEXT, at REAL, state TEXT);
            CREATE TABLE IF NOT EXISTS episodes (
              incident_id TEXT, evidence_hash TEXT, at REAL, state TEXT, result TEXT,
              PRIMARY KEY (incident_id,evidence_hash));
            CREATE TABLE IF NOT EXISTS notification_audit (
              seq INTEGER PRIMARY KEY, at REAL, notification_id TEXT, decision TEXT, reason TEXT);
            PRAGMA user_version=8;
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT COUNT(*) FROM notification_audit").fetchone()[0] >= MAX_AUDIT:
                raise ValueError("notification_journal_capacity")
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit(self, notice, decision, reason):
        self.db.execute("INSERT INTO notification_audit(at,notification_id,decision,reason) VALUES (?,?,?,?)",
                        (self.clock(), notice, decision, reason))

    def reject(self, code, notice=None):
        try:
            with self.transaction():
                self.audit(notice, "rejected", code)
        except (sqlite3.Error, ValueError):
            code = "notification_journal_unavailable"
        return {"status": "rejected", "reason": code, "diagnosis": None, "execution_allowed": False}

    def handle(self, event, bundle):
        try:
            event = parse_event(event, self.clock())
        except (ValueError, TypeError, OverflowError):
            return self.reject("invalid_stale_or_future_notification")
        notice, incident = event["notification_id"], event["incident_id"]
        try:
            validate_bundle(bundle)
            if not 0 <= self.clock()-bundle.as_of <= 15:
                raise ValueError("Stale bundle")
            bundle = deepcopy(bundle)
            event_hash = hashlib.sha256(encoded(event).encode()).hexdigest()
            # Exclude moving envelope time; identical observations are one episode.
            records = sorted(bundle.document()["records"], key=lambda r:r["id"])
            fingerprint = hashlib.sha256(encoded(records).encode()).hexdigest()
        except (ValueError, TypeError, AttributeError, KeyError, OverflowError, RecursionError):
            return self.reject("invalid_or_stale_evidence", notice)
        try:
            with self.transaction():
                prior = self.db.execute("SELECT event_hash FROM inbox WHERE notification_id=?", (notice,)).fetchone()
                if prior:
                    status = "duplicate_notification" if prior[0] == event_hash else "notification_id_collision"
                    self.audit(notice, "suppressed" if prior[0] == event_hash else "rejected", status)
                    return {"status": "suppressed" if prior[0] == event_hash else "rejected", "reason": status,
                            "diagnosis": None, "execution_allowed": False}
                if self.db.execute("SELECT COUNT(*) FROM inbox").fetchone()[0] >= MAX_EVENTS:
                    raise ValueError("notification_journal_capacity")
                prior_episode = self.db.execute("SELECT state FROM episodes WHERE incident_id=? AND evidence_hash=?",
                                                (incident, fingerprint)).fetchone()
                state = "duplicate_evidence" if prior_episode else "pending"
                self.db.execute("INSERT INTO inbox VALUES (?,?,?,?,?,?)",
                                (notice,event_hash,incident,fingerprint,self.clock(),state))
                if prior_episode:
                    self.audit(notice, "suppressed", "duplicate_evidence")
                    return {"status":"suppressed", "reason":"duplicate_evidence", "diagnosis":None, "execution_allowed":False}
                self.db.execute("INSERT INTO episodes VALUES (?,?,?,?,NULL)", (incident,fingerprint,self.clock(),"pending"))
                self.audit(notice, "claimed", "intent_durably_recorded")
        except (sqlite3.Error, ValueError):
            return self.reject("notification_journal_unavailable", notice)
        try:
            diagnosis = self.agent.diagnose(bundle)
            payload = encoded(diagnosis)
            if diagnosis.get("execution_allowed") is not False or len(payload.encode()) > 4_000_000:
                raise ValueError("Unsafe diagnosis output")
        except Exception:
            try:
                with self.transaction():
                    self.db.execute("UPDATE episodes SET state='uncertain' WHERE incident_id=? AND evidence_hash=?", (incident,fingerprint))
                    self.db.execute("UPDATE inbox SET state='uncertain' WHERE notification_id=?", (notice,))
                    self.audit(notice, "rejected", "diagnosis_failed_no_retry")
            except (sqlite3.Error, ValueError):
                pass  # The durable pending claim still suppresses a retry.
            return {"status":"rejected", "reason":"diagnosis_failed_no_retry", "diagnosis":None, "execution_allowed":False}
        try:
            with self.transaction():
                self.db.execute("UPDATE episodes SET state='complete',result=? WHERE incident_id=? AND evidence_hash=?", (payload,incident,fingerprint))
                self.db.execute("UPDATE inbox SET state='complete' WHERE notification_id=?", (notice,))
                self.audit(notice, "diagnosed", "result_persisted")
        except (sqlite3.Error, ValueError):
            return {"status":"rejected", "reason":"result_persistence_failed", "diagnosis":None, "execution_allowed":False}
        return {"status":"diagnosed", "reason":"new_evidence", "diagnosis":diagnosis, "execution_allowed":False}
