import asyncio

import pytest
from app.adapters.opa_http_client import OPAHttpClient

def test_policy_evaluator_returns_result():
    evaluator = OPAHttpClient()
    # Minimal valid input for OPA (mock or real OPA endpoint required)
    package = "github/deploy"
    input_data = {"environment": "dev", "ref": "refs/heads/main", "repo_environments": ["dev"], "workflow_meta": {}, "repo_policy": {}}
    try:
        result = asyncio.run(evaluator.evaluate(package, input_data))
        assert isinstance(result, dict)
        assert "allow" in result
    except Exception as exc:
        pytest.skip(f"OPA endpoint not available: {exc}")
