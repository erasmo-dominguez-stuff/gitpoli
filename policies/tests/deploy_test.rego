package github.deploy_test

import rego.v1

# =============================================================================
#  Tests for the deployment protection policy (github.deploy)
# =============================================================================

test_allow_production_valid if {
	inp := {
		"environment": "production",
		"ref": "refs/heads/main",
		"repo_environments": ["production", "staging"],
		"workflow_meta": {
			"approvers": ["alice", "bob"],
			"checks": {"tests": true},
			"signed_off": true,
			"deployments_today": 1,
		},
		"repo_policy": {"policy": {
			"version": "1.0.0",
			"environments": {"production": {
				"enabled": true,
				"rules": {
					"approvals_required": 2,
					"allowed_branches": ["main"],
					"tests_passed": true,
					"signed_off": true,
					"max_deployments_per_day": 5,
				},
			}},
		}},
	}

	vs := data.github.deploy.violations with input as inp
	count(vs) == 0
	allow := data.github.deploy.allow with input as inp
	allow == true
}

test_branch_not_allowed_produces_ref_denied if {
	inp := {
		"environment": "production",
		"ref": "refs/heads/feature/xyz",
		"repo_environments": ["production"],
		"workflow_meta": {
			"approvers": ["alice", "bob"],
			"checks": {"tests": true},
			"signed_off": true,
			"deployments_today": 0,
		},
		"repo_policy": {"policy": {
			"version": "1.0.0",
			"environments": {"production": {
				"enabled": true,
				"rules": {
					"approvals_required": 2,
					"allowed_branches": ["main"],
					"tests_passed": true,
					"signed_off": true,
					"max_deployments_per_day": 5,
				},
			}},
		}},
	}

	vs := data.github.deploy.violations with input as inp
	some i
	vs[i].code == "ref.denied"
}

test_deny_missing_approvers if {
	inp := {
		"environment": "production",
		"ref": "refs/heads/main",
		"repo_environments": ["production"],
		"workflow_meta": {
			"approvers": [],
			"checks": {"tests": true},
			"signed_off": true,
			"deployments_today": 0,
		},
		"repo_policy": {"policy": {
			"version": "1.0.0",
			"environments": {"production": {
				"enabled": true,
				"rules": {
					"approvals_required": 2,
					"allowed_branches": ["main"],
					"tests_passed": true,
					"signed_off": true,
					"max_deployments_per_day": 5,
				},
			}},
		}},
	}

	vs := data.github.deploy.violations with input as inp
	some i
	vs[i].code == "approvals.insufficient"
}

test_deny_tests_not_passed if {
	inp := {
		"environment": "production",
		"ref": "refs/heads/main",
		"repo_environments": ["production"],
		"workflow_meta": {
			"approvers": ["alice", "bob"],
			"checks": {"tests": false},
			"signed_off": true,
			"deployments_today": 0,
		},
		"repo_policy": {"policy": {
			"version": "1.0.0",
			"environments": {"production": {
				"enabled": true,
				"rules": {
					"approvals_required": 2,
					"allowed_branches": ["main"],
					"tests_passed": true,
					"signed_off": true,
					"max_deployments_per_day": 5,
				},
			}},
		}},
	}

	vs := data.github.deploy.violations with input as inp
	some i
	vs[i].code == "tests.failed"
}

test_deny_rate_limit_exceeded if {
	inp := {
		"environment": "production",
		"ref": "refs/heads/main",
		"repo_environments": ["production"],
		"workflow_meta": {
			"approvers": ["alice", "bob"],
			"checks": {"tests": true},
			"signed_off": true,
			"deployments_today": 10,
		},
		"repo_policy": {"policy": {
			"version": "1.0.0",
			"environments": {"production": {
				"enabled": true,
				"rules": {
					"approvals_required": 2,
					"allowed_branches": ["main"],
					"tests_passed": true,
					"signed_off": true,
					"max_deployments_per_day": 5,
				},
			}},
		}},
	}

	vs := data.github.deploy.violations with input as inp
	some i
	vs[i].code == "rate_limit.exceeded"
}
