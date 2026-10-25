"""Fixed read-only tools. No arbitrary SQL, PromQL, URLs, shell or cluster credentials."""
import json
from pathlib import Path
import sqlite3

from services.diagnosis.evidence import Aggregator, MAX_INPUT, timestamp
from services.incidents.telemetry import Collector


class IncidentTools:
    def __init__(self, database):
        path = Path(database).resolve(strict=True)
        self.db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA query_only=ON")
        if self.db.execute("PRAGMA user_version").fetchone()[0] != 1:
            self.close()
            raise ValueError("Unsupported incident schema")

    def close(self):
        self.db.close()

    def list_incidents(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Incident limit must be 1..100")
        return [dict(r) for r in self.db.execute(
            "SELECT id,service,rule,state,opened_at,updated_at FROM incidents ORDER BY detected_at DESC,id LIMIT ?", (limit,))]

    def get_incident(self, incident_id):
        if not isinstance(incident_id, str) or len(incident_id) > 128:
            raise ValueError("Invalid incident ID")
        row = self.db.execute("SELECT id,service,rule,state,opened_at,updated_at FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return dict(row) if row else None

    def aggregate(self, incident_id, as_of):
        item = self.get_incident(incident_id)
        if item is None:
            raise ValueError("Incident not found")
        at = timestamp(as_of)
        agg = Aggregator(at)
        # Read an atomic snapshot, not a moving mix of independently fetched evidence rows.
        self.db.execute("BEGIN")
        try:
            rows = self.db.execute(
                "SELECT at,document FROM evidence WHERE at>=? AND at<=? ORDER BY at DESC LIMIT 32",
                (max(item["opened_at"] or 0, at-120), at)).fetchall()
            for row in reversed(rows):
                if len(row["document"].encode()) > MAX_INPUT:
                    raise ValueError("Oversized incident evidence")
                agg.snapshot(json.loads(row["document"]))
        finally:
            self.db.rollback()
        return agg.finish()


class TelemetryTools:
    def __init__(self, url="http://127.0.0.1:19090", transport=None):
        self.collector = Collector(url, transport=transport)

    def collect(self):
        return self.collector.collect().document()


def execute_tool(tools, name, arguments):
    """Dispatch only the exact schema; unknown names/keys never become executable text."""
    allowed = {"list_incidents": ("limit",), "get_incident": ("incident_id",),
               "aggregate": ("incident_id", "as_of")}
    if name not in allowed or not isinstance(arguments, dict) or set(arguments) != set(allowed[name]):
        raise ValueError("Tool name or arguments are not allowlisted")
    return getattr(tools, name)(**arguments)
