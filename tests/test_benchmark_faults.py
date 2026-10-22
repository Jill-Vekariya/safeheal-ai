"""Safety and actual HTTP behaviour of opt-in, expiring business faults."""
import asyncio
import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from services.app import create_app
from services import benchmark_faults as faults


@pytest.fixture
def lease_path(tmp_path, monkeypatch):
    path = tmp_path / "lease.json"
    monkeypatch.setenv("SAFEHEAL_FAULTS_ENABLED", "local-test")
    monkeypatch.setenv("SAFEHEAL_FAULT_FILE", str(path))
    return path


def lease(**changes):
    return {"schema_version": 1, "trial_id": "trial-001", "scenario": "latency",
            "activated_at": 100.0, "expires_at": 120.0, "delay_seconds": 1.25, **changes}


def write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")


def test_disabled_default_control_path_is_platform_absolute(monkeypatch):
    monkeypatch.delenv("SAFEHEAL_FAULTS_ENABLED", raising=False)
    monkeypatch.setenv("SAFEHEAL_FAULT_FILE", "relative-path-is-ignored-when-disabled.json")
    control = faults.FaultControl.from_env()
    assert control.path == faults.DEFAULT_PATH
    assert control.path.is_absolute()
    assert not control.enabled
    assert control.current() is None


@pytest.mark.parametrize("setting", [None, "true", "1", "production", "LOCAL-TEST"])
def test_faults_require_exact_opt_in(lease_path, monkeypatch, setting):
    faults.activate("trial-001", "http_5xx", 30, path=lease_path)
    if setting is None:
        monkeypatch.delenv("SAFEHEAL_FAULTS_ENABLED")
    else:
        monkeypatch.setenv("SAFEHEAL_FAULTS_ENABLED", setting)
    assert not faults.enabled()
    assert faults.configured_path() == faults.DEFAULT_PATH
    with TestClient(create_app("payment")) as client:
        result = client.post("/payments", json={"order_id": "healthy", "amount_cents": 2000})
        assert result.status_code == 201
        assert "x-safeheal-fault-id" not in result.headers
    with pytest.raises(RuntimeError, match="requires"):
        faults.activate("trial-002", "http_5xx", 10, path=lease_path)


def test_error_fault_only_affects_payment_business_requests(lease_path):
    ack = faults.activate("trial-001", "http_5xx", 30, path=lease_path)
    assert ack["applied"] and ack["expires_at"] - ack["activated_at"] == 30
    assert ack["delay_seconds"] == 0
    with TestClient(create_app("payment")) as client:
        for path in ("/healthz", "/readyz", "/metrics"):
            response = client.get(path)
            assert response.status_code == 200
            assert "x-safeheal-fault-id" not in response.headers
        bad = client.post("/payments", json={"order_id": "trial", "amount_cents": 2000})
        assert bad.status_code == 500
        assert bad.headers["x-safeheal-fault-id"] == "trial-001"
        assert bad.headers["x-safeheal-fault-scenario"] == "http_5xx"
        assert client.post("/payments", json={"amount_cents": -1}).status_code == 422
        metrics = client.get("/metrics").text
        assert 'status_class="5xx"' in metrics
        faults.remove("trial-001", path=lease_path)
        result = client.post("/payments", json={"order_id": "recovered", "amount_cents": 2000})
        assert result.status_code == 201
        assert "x-safeheal-fault-id" not in result.headers


def test_latency_retains_receipt_and_does_not_block_health(lease_path):
    faults.activate("trial-001", "latency", 30, delay_seconds=0.10, path=lease_path)
    async def requests():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app("payment")),
                                     base_url="http://local-test", trust_env=False) as client:
            pending = asyncio.create_task(client.post("/payments", json={"order_id": "slow", "amount_cents": 2000}))
            # Let the business request reach its asynchronous injected sleep.
            await asyncio.sleep(0)
            health = await client.get("/healthz")
            assert health.status_code == 200
            assert not pending.done()
            result = await pending
            assert result.status_code == 201
            assert result.json()["status"] == "simulated_paid"
            assert result.headers["x-safeheal-fault-scenario"] == "latency"
    asyncio.run(requests())


def test_non_payment_role_has_no_fault_hook(lease_path):
    faults.activate("trial-001", "http_5xx", 30, path=lease_path)
    def downstream(request):
        body = json.loads(request.content)
        return httpx.Response(201, json={**body, "order_id": "order", "amount_cents": 2000,
                                        "payment_id": "payment", "status": "confirmed"})
    with TestClient(create_app("gateway", "http://order", httpx.MockTransport(downstream))) as client:
        result = client.post("/orders", json={"item_id": "demo", "quantity": 2})
        assert result.status_code == 201
        assert "x-safeheal-fault-id" not in result.headers


def test_expiry_enforced_without_runner_cleanup(lease_path):
    clock = {"wall": 100.0, "mono": 10.0}
    write(lease_path, lease())
    control = faults.FaultControl(enabled=True, path=lease_path,
                                  wall_clock=lambda: clock["wall"], monotonic_clock=lambda: clock["mono"])
    assert control.current().trial_id == "trial-001"
    clock.update(wall=120.0, mono=30.0)
    assert control.current() is None
    assert lease_path.exists()  # No external cleanup was needed for expiry.


def test_wall_clock_reversal_cannot_extend_monotonic_deadline(lease_path):
    clock = {"wall": 105.0, "mono": 10.0}
    write(lease_path, lease())
    control = faults.FaultControl(enabled=True, path=lease_path,
                                  wall_clock=lambda: clock["wall"], monotonic_clock=lambda: clock["mono"])
    assert control.current().remaining_seconds == 15
    clock.update(wall=101.0, mono=26.0)
    assert control.current() is None
    clock.update(wall=106.0, mono=27.0)
    assert control.current() is None


def test_changed_lease_cannot_extend_existing_trial(lease_path):
    write(lease_path, lease())
    control = faults.FaultControl(enabled=True, path=lease_path, wall_clock=lambda: 105.0,
                                  monotonic_clock=lambda: 10.0)
    assert control.current() is not None
    write(lease_path, lease(expires_at=130.0))
    assert control.current() is None
    write(lease_path, lease())
    assert control.current() is None


@pytest.mark.parametrize("changes", [
    {"schema_version": True}, {"schema_version": 2}, {"trial_id": "bad/id"},
    {"trial_id": "a" * 81}, {"scenario": "shell"}, {"scenario": []},
    {"activated_at": 110}, {"expires_at": 100}, {"expires_at": 221},
    {"expires_at": float("inf")}, {"delay_seconds": float("nan")},
    {"delay_seconds": True}, {"delay_seconds": 0}, {"delay_seconds": 1.51},
    {"scenario": "http_5xx", "delay_seconds": 0.1}, {"extra": "ignored?"},
])
def test_invalid_or_future_lease_cannot_inject(lease_path, changes):
    write(lease_path, lease(**changes))
    control = faults.FaultControl(enabled=True, path=lease_path, wall_clock=lambda: 105.0)
    assert control.current() is None


@pytest.mark.parametrize("data", ["{", "[]", "x" * 4097,
                                  '{"schema_version":1,"schema_version":1}'])
def test_malformed_oversized_or_duplicate_data_cannot_inject(lease_path, data):
    lease_path.write_text(data, encoding="utf-8")
    assert faults.FaultControl(enabled=True, path=lease_path).current() is None


def test_directory_control_cannot_block_or_inject(lease_path):
    lease_path.mkdir()
    assert faults.FaultControl(enabled=True, path=lease_path).current() is None


def test_symlink_control_is_not_followed(lease_path, tmp_path):
    target = tmp_path / "other.json"
    write(target, lease())
    try:
        lease_path.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable for this test user")
    assert faults.FaultControl(enabled=True, path=lease_path, wall_clock=lambda: 105.0).current() is None
    with pytest.raises(ValueError, match="regular file"):
        faults.remove("trial-001", path=lease_path)
    assert target.exists()


@pytest.mark.parametrize("duration", [0, -1, 121, float("inf"), float("nan"), True, "45"])
def test_invalid_duration_fails_before_file_creation(lease_path, duration):
    with pytest.raises(ValueError):
        faults.activate("trial-001", "http_5xx", duration, path=lease_path)
    assert not lease_path.exists()


def test_activation_cannot_overwrite_lease(lease_path):
    faults.activate("trial-001", "http_5xx", 30, path=lease_path)
    original = lease_path.read_bytes()
    with pytest.raises(FileExistsError):
        faults.activate("trial-002", "latency", 30, path=lease_path)
    assert lease_path.read_bytes() == original
    assert not lease_path.with_name(lease_path.name + ".lock").exists()


def test_competing_control_writer_refuses_existing_lock(lease_path):
    lock = lease_path.with_name(lease_path.name + ".lock")
    lock.write_text("another owner", encoding="utf-8")
    with pytest.raises(FileExistsError):
        faults.activate("trial-001", "http_5xx", 30, path=lease_path)
    assert lock.read_text() == "another owner"
    assert not lease_path.exists()


def test_cleanup_only_removes_matching_id_and_is_idempotent(lease_path):
    faults.activate("trial-001", "http_5xx", 30, path=lease_path)
    with pytest.raises(RuntimeError, match="different trial"):
        faults.remove("trial-002", path=lease_path)
    assert lease_path.exists()
    assert faults.remove("trial-001", path=lease_path)["removed"]
    assert faults.remove("trial-001", path=lease_path)["already_absent"]


def test_cleanup_refuses_malformed_file(lease_path):
    lease_path.write_text("garbage", encoding="utf-8")
    with pytest.raises(ValueError):
        faults.remove("trial-001", path=lease_path)
    assert lease_path.read_text() == "garbage"


def test_relative_path_rejected(lease_path):
    with pytest.raises(ValueError, match="absolute"):
        faults.activate("trial-001", "http_5xx", 10, path=Path("relative.json"))
