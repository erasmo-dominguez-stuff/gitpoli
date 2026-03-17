# conftest.py for shared fixtures
import pytest

@pytest.fixture
def sample_policy_config():
    return {
        "approvals_required": 2,
        "allowed_branches": ["main"],
        "tests_passed": True,
        "signed_off": True,
        "max_deployments_per_day": 5
    }

@pytest.fixture
def sample_event():
    return {
        "deployment": {
            "ref": "main",
            "environment": "production"
        },
        "environment": "production"
    }
