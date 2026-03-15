package github.deploy

import rego.v1

import data.lib.helpers

# =============================================================================
#  GitHub Deployment Protection Policy
#
#  Evaluates deployment requests against team-defined rules for each
#  environment (approvals, allowed branches, tests, sign-off, rate).
#
#  Entrypoints: github/deploy/allow, github/deploy/violations
# =============================================================================

# ── Final decision ────────────────────────────────────────────────────────────

default allow := false

allow if count(violations) == 0

# ── Aggregate violations ─────────────────────────────────────────────────────

violations contains v if v := input_schema_violations[_]

violations contains v if v := policy_schema_violations[_]

violations contains v if v := environment_missing_violations[_]

violations contains v if v := branch_violations[_]

violations contains v if v := approval_violations[_]

violations contains v if v := ci_violations[_]

violations contains v if v := signoff_violations[_]

violations contains v if v := rate_limit_violations[_]

# ── Derived config ───────────────────────────────────────────────────────────

env_config := input.repo_policy.policy.environments[input.environment] if {
	helpers.has_env_in_policy(input)
}

rules := env_config.rules if {
	env_config
	env_config.rules
}

# ========== A) INPUT SCHEMA VALIDATION ========================================

input_schema_violations contains v if {
	not input.environment
	v := {"code": "schema.input.missing_environment", "msg": "Missing input.environment"}
}

input_schema_violations contains v if {
	not input.ref
	v := {"code": "schema.input.missing_ref", "msg": "Missing input.ref (e.g., refs/heads/main)"}
}

input_schema_violations contains v if {
	not input.repo_environments
	v := {"code": "schema.input.missing_repo_environments", "msg": "Missing input.repo_environments (array of env names)"}
}

input_schema_violations contains v if {
	not input.workflow_meta
	v := {"code": "schema.input.missing_workflow_meta", "msg": "Missing input.workflow_meta"}
}

input_schema_violations contains v if {
	input.workflow_meta
	wm := input.workflow_meta
	wm.checks
	not helpers.type_bool_strict(wm.checks.tests)
	v := {"code": "schema.input.invalid_checks.tests", "msg": "workflow_meta.checks.tests must be boolean"}
}

input_schema_violations contains v if {
	input.workflow_meta
	wm := input.workflow_meta
	wm.approvers
	not helpers.is_array_of_strings(wm.approvers)
	v := {"code": "schema.input.invalid_approvers", "msg": "workflow_meta.approvers must be array of strings"}
}

input_schema_violations contains v if {
	input.workflow_meta
	wm := input.workflow_meta
	wm.deployments_today
	not helpers.type_number(wm.deployments_today)
	v := {"code": "schema.input.invalid_deployments_today", "msg": "workflow_meta.deployments_today must be number"}
}

# ========== B) POLICY SCHEMA VALIDATION =======================================

policy_schema_violations contains v if {
	not input.repo_policy
	v := {"code": "schema.policy.missing_repo_policy", "msg": "Missing input.repo_policy"}
}

policy_schema_violations contains v if {
	input.repo_policy
	not input.repo_policy.policy
	v := {"code": "schema.policy.missing_policy", "msg": "Missing input.repo_policy.policy"}
}

policy_schema_violations contains v if {
	input.repo_policy.policy
	not helpers.type_string(input.repo_policy.policy.version)
	v := {"code": "schema.policy.missing_version", "msg": "policy.version must be string"}
}

policy_schema_violations contains v if {
	input.repo_policy.policy
	not input.repo_policy.policy.environments
	v := {"code": "schema.policy.missing_environments", "msg": "policy.environments missing"}
}

policy_schema_violations contains v if {
	input.repo_policy.policy.environments
	not input.repo_policy.policy.environments[input.environment]
	v := {"code": "schema.policy.env_not_defined", "msg": sprintf("Environment %q not found in policy.environments", [input.environment])}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	cfg := input.repo_policy.policy.environments[input.environment]
	not helpers.type_boolean(cfg.enabled)
	v := {"code": "schema.policy.env.enabled", "msg": "environments[env].enabled must be boolean"}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	cfg := input.repo_policy.policy.environments[input.environment]
	not cfg.rules
	v := {"code": "schema.policy.env.rules.missing", "msg": "environments[env].rules missing"}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	r := input.repo_policy.policy.environments[input.environment].rules
	not helpers.type_number(r.approvals_required)
	v := {"code": "schema.policy.rules.approvals_required", "msg": "rules.approvals_required must be number"}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	r := input.repo_policy.policy.environments[input.environment].rules
	r.allowed_branches != null
	not helpers.is_array_of_strings(r.allowed_branches)
	v := {"code": "schema.policy.rules.allowed_branches", "msg": "rules.allowed_branches must be array of strings or null"}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	r := input.repo_policy.policy.environments[input.environment].rules
	not helpers.type_boolean(r.tests_passed)
	v := {"code": "schema.policy.rules.tests_passed", "msg": "rules.tests_passed must be boolean"}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	r := input.repo_policy.policy.environments[input.environment].rules
	not helpers.type_boolean(r.signed_off)
	v := {"code": "schema.policy.rules.signed_off", "msg": "rules.signed_off must be boolean"}
}

policy_schema_violations contains v if {
	helpers.has_env_in_policy(input)
	r := input.repo_policy.policy.environments[input.environment].rules
	not helpers.type_number(r.max_deployments_per_day)
	v := {"code": "schema.policy.rules.max_deployments_per_day", "msg": "rules.max_deployments_per_day must be number"}
}

# ========== C) BUSINESS RULES ================================================

environment_missing_violations contains v if {
	env_config
	env_config.enabled
	not helpers.env_in_repo(input.environment, input.repo_environments)
	v := {"code": "env.missing", "msg": sprintf("Environment %q not defined in repository", [input.environment])}
}

branch_violations contains v if {
	rules
	rules.allowed_branches != null
	not helpers.branch_allowed(rules.allowed_branches, input.ref)
	v := {"code": "ref.denied", "msg": sprintf("Branch %s not allowed for environment %s. Allowed: %v", [input.ref, input.environment, rules.allowed_branches])}
}

approval_violations contains v if {
	rules
	rules.approvals_required > 0
	approvers := helpers.safe_array(input.workflow_meta.approvers)
	count(approvers) < rules.approvals_required
	v := {"code": "approvals.insufficient", "msg": sprintf("Environment %s requires %d approvers, but only %d provided", [input.environment, rules.approvals_required, count(approvers)])}
}

ci_violations contains v if {
	rules
	rules.tests_passed
	not has_tests_true(input.workflow_meta)
	v := {"code": "tests.failed", "msg": sprintf("Tests must pass for %s environment deployment", [input.environment])}
}

signoff_violations contains v if {
	rules
	rules.signed_off
	not helpers.truthy(input.workflow_meta.signed_off)
	v := {"code": "signoff.missing", "msg": sprintf("Sign-off required for %s environment deployment", [input.environment])}
}

rate_limit_violations contains v if {
	rules
	rules.max_deployments_per_day > 0
	dtoday := helpers.number_or_zero(input.workflow_meta.deployments_today)
	dtoday > rules.max_deployments_per_day
	v := {"code": "rate_limit.exceeded", "msg": sprintf("Daily deployment limit exceeded for %s. Max: %d, Attempted: %d", [input.environment, rules.max_deployments_per_day, dtoday])}
}

# ── Policy-specific helpers (not shared) ─────────────────────────────────────

has_tests_true(wf) if {
	wf
	wf.checks
	helpers.truthy(wf.checks.tests)
}
