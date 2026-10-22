"""Bounded, opt-in business faults for the isolated SafeHeal benchmark.

The application only reads a small data lease. It exposes no control endpoint,
executes no supplied code, and never changes probes or telemetry endpoints.
The developer harness writes/removes leases through authenticated local exec.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time

VERSION = "day5-v1"
SCHEMA_VERSION = 1
# Kubernetes runs Linux and keeps one fixed, scoped control path. Windows local
# tests need an absolute drive-qualified temporary path even when faults are off.
DEFAULT_PATH = (Path(tempfile.gettempdir()) if os.name == "nt" else Path("/tmp")) / "safeheal-benchmark-fault.json"
MAX_BYTES = 4096
MAX_LIFETIME_SECONDS = 120.0
MAX_DELAY_SECONDS = 1.5
SCENARIOS = frozenset({"http_5xx", "latency"})
_FIELDS = {"schema_version", "trial_id", "scenario", "activated_at", "expires_at", "delay_seconds"}
_TRIAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def enabled():
    return os.environ.get("SAFEHEAL_FAULTS_ENABLED") == "local-test"


def configured_path():
    # A custom path supports separate local-process laboratories. The override
    # does not enable faults and is ignored when explicit opt-in is absent.
    return _path(os.environ.get("SAFEHEAL_FAULT_FILE", str(DEFAULT_PATH))) if enabled() else DEFAULT_PATH


def _path(path):
    result = Path(path)
    if not result.is_absolute():
        raise ValueError("Fault lease path must be absolute")
    return result


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def _trial_id(value):
    if not isinstance(value, str) or not _TRIAL.fullmatch(value):
        raise ValueError("Invalid trial_id")
    return value


def _validate(document):
    if not isinstance(document, dict) or set(document) != _FIELDS:
        raise ValueError("Invalid fault lease fields")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported fault lease schema")
    _trial_id(document["trial_id"])
    if document["scenario"] not in SCENARIOS:
        raise ValueError("Unknown fault scenario")
    start = _number(document["activated_at"], "activation")
    end = _number(document["expires_at"], "expiry")
    delay = _number(document["delay_seconds"], "delay")
    if start <= 0 or not 0 < end - start <= MAX_LIFETIME_SECONDS:
        raise ValueError("Fault lifetime must be positive and at most 120 seconds")
    if document["scenario"] == "latency" and not 0 < delay <= MAX_DELAY_SECONDS:
        raise ValueError("Latency must be positive and at most 1.5 seconds")
    if document["scenario"] == "http_5xx" and delay != 0:
        raise ValueError("HTTP error leases cannot include latency")
    return document


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate fault lease field")
        result[key] = value
    return result


def _read(path):
    # Reject symlinks, directories and devices rather than following a control
    # file into another location or blocking on a pipe. O_NOFOLLOW closes the
    # symlink race on platforms that provide it; lstat is also used on Windows.
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("Fault lease must be a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("Invalid fault lease file")
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Oversized fault lease")
    document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    return _validate(document), raw


@contextmanager
def _control_lock(path):
    # Shared across harness processes. A stale lock is never silently removed.
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink()


def activate(trial_id, scenario, duration_seconds, delay_seconds=1.25, path=DEFAULT_PATH):
    """Create one immutable lease, using the target process's clock.

    Refuse an existing lease, even if expired. The owner must remove it by its
    exact trial ID first. No retry or replacement can extend an active fault.
    """
    if not enabled():
        raise RuntimeError("Fault injection requires SAFEHEAL_FAULTS_ENABLED=local-test")
    path = _path(path)
    duration = _number(duration_seconds, "duration")
    if not 0 < duration <= MAX_LIFETIME_SECONDS:
        raise ValueError("Fault duration must be positive and at most 120 seconds")
    now = time.time()
    document = _validate({"schema_version": SCHEMA_VERSION, "trial_id": trial_id,
                          "scenario": scenario, "activated_at": now,
                          "expires_at": now + duration,
                          "delay_seconds": delay_seconds if scenario == "latency" else 0.0})
    data = json.dumps(document, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    with _control_lock(path):
        if path.exists() or path.is_symlink():
            raise FileExistsError("A fault lease already exists; remove only its known trial ID")
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".",
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {**document, "path": str(path), "applied": True}


def remove(trial_id, path=DEFAULT_PATH):
    """Remove only the expected lease; missing is an idempotent success."""
    _trial_id(trial_id)
    path = _path(path)
    if not path.parent.exists():
        return {"trial_id": trial_id, "path": str(path), "removed": False, "already_absent": True}
    with _control_lock(path):
        try:
            document, _ = _read(path)
        except FileNotFoundError:
            return {"trial_id": trial_id, "path": str(path), "removed": False, "already_absent": True}
        if document["trial_id"] != trial_id:
            raise RuntimeError("Refusing to remove a different trial's fault lease")
        path.unlink()
    return {"trial_id": trial_id, "path": str(path), "removed": True, "already_absent": False}


@dataclass(frozen=True)
class ActiveFault:
    trial_id: str
    scenario: str
    delay_seconds: float
    remaining_seconds: float

    @property
    def headers(self):
        return {"x-safeheal-fault-id": self.trial_id,
                "x-safeheal-fault-scenario": self.scenario}


class FaultControl:
    def __init__(self, *, enabled=False, path=DEFAULT_PATH, wall_clock=time.time,
                 monotonic_clock=time.monotonic):
        self.enabled, self.path = enabled, _path(path)
        self.wall_clock, self.monotonic_clock = wall_clock, monotonic_clock
        self._lock = threading.Lock()
        self._raw = None
        self._trial = None
        self._deadline = None
        self._retired = set()

    @classmethod
    def from_env(cls):
        return cls(enabled=enabled(), path=configured_path())

    def current(self):
        if not self.enabled:
            return None
        with self._lock:
            try:
                document, raw = _read(self.path)
                wall, monotonic = self.wall_clock(), self.monotonic_clock()
                if not document["activated_at"] <= wall < document["expires_at"]:
                    return None
                trial = document["trial_id"]
                if trial in self._retired:
                    return None
                if raw != self._raw:
                    if trial == self._trial:
                        # A trial's data is immutable, including its deadline.
                        self._retired.add(trial)
                        return None
                    if self._trial is not None:
                        self._retired.add(self._trial)
                    self._trial, self._raw = trial, raw
                    self._deadline = monotonic + min(document["expires_at"] - wall, MAX_LIFETIME_SECONDS)
                remaining = min(document["expires_at"] - wall, self._deadline - monotonic)
                if remaining <= 0:
                    self._retired.add(trial)
                    return None
                return ActiveFault(trial, document["scenario"], float(document["delay_seconds"]), remaining)
            except (OSError, ValueError, TypeError, KeyError, UnicodeError):
                # Missing or invalid controls cannot turn ordinary requests into
                # faults. The runner independently verifies successful activation.
                return None
