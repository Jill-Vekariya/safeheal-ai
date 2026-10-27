"""Regression checks for response accumulation and pre-decode rejection."""
import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def evaluator():
    import sys
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("provider_boundary", SCRIPTS / "evaluate_provider_boundary.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.mark.parametrize("name,expected", [
    ("response_oversize", "provider_response_too_large"),
    ("compressed_valid", "provider_unsupported_encoding"),
    ("kubernetes_oversize", "kubernetes_response_too_large"),
    ("kubernetes_compressed", "kubernetes_response_encoding"),
    ("slow_trickle", "provider_timeout"),
])
def test_boundary_failure_is_early_bounded_and_closed(tmp_path, name, expected):
    result = evaluator().fixture(name, expected, tmp_path / name)
    assert result["passed"], result
    if name == "slow_trickle":
        assert result["stream_chunks"] <= 2
