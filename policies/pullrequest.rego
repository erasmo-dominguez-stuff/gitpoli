package github.pullrequest

import rego.v1

import data.lib.helpers

# =============================================================================
#  GitHub Pull Request Policy
#
#  Evaluates PR events against team-defined rules
#  (branch naming, target branch, approvals, sign-off).
#
#  Entrypoints: github/pullrequest/allow, github/pullrequest/violations
# =============================================================================

# ── Final decision ────────────────────────────────────────────────────────────

default allow := false

allow if count(violations) == 0

# ── Aggregate violations ─────────────────────────────────────────────────────

violations contains v if v := policy_missing_violations[_]

violations contains v if v := branch_naming_violations[_]

violations contains v if v := target_branch_violations[_]

violations contains v if v := approval_violations[_]

violations contains v if v := signoff_violations[_]

# ── Derived config ───────────────────────────────────────────────────────────

rules := input.repo_policy.policy.rules

branch_rules := helpers.safe_array(input.repo_policy.policy.branch_rules)

# ========== BUSINESS RULES ===================================================

# 1) Policy must exist with a rules section.
policy_missing_violations contains v if {
	not input.repo_policy.policy.rules
	v := {"code": "policy.missing", "msg": "Pull request policy or rules section missing in repo_policy"}
}

# 2) Branch naming convention: if branch_rules are defined, the PR
#    source→target must match at least one rule.
branch_naming_violations contains v if {
	count(branch_rules) > 0
	input.head_ref
	input.base_ref
	source := helpers.strip_refs_prefix(input.head_ref)
	target := helpers.strip_refs_prefix(input.base_ref)
	not helpers.branch_rule_matches(branch_rules, source, target)
	v := {"code": "branch_naming.denied", "msg": sprintf("Branch %q → %q does not match any allowed branch naming rule", [source, target])}
}

# 3) The PR target branch must be in the allowed list.
target_branch_violations contains v if {
	rules
	rules.allowed_target_branches != null
	target := helpers.strip_refs_prefix(input.base_ref)
	not target_in_allowed(rules.allowed_target_branches, target)
	v := {"code": "target_branch.denied", "msg": sprintf("Target branch %q not in allowed list: %v", [target, rules.allowed_target_branches])}
}

# ── Policy-specific helpers (not shared) ─────────────────────────────────────

target_in_allowed(allowed, branch) if {
	some b in helpers.safe_array(allowed)
	helpers.branch_name_matches(b, branch)
}

# 4) Approvals: require a minimum number of distinct approvers.
approval_violations contains v if {
	rules
	rules.approvals_required > 0
	approvers := helpers.safe_array(input.workflow_meta.approvers)
	count(approvers) < rules.approvals_required
	v := {"code": "approvals.insufficient", "msg": sprintf("Requires %d approvers, but only %d provided", [rules.approvals_required, count(approvers)])}
}

# 5) Sign-off: require DCO-style sign-off if configured.
signoff_violations contains v if {
	rules
	rules.signed_off
	not helpers.truthy(input.workflow_meta.signed_off)
	v := {"code": "signoff.missing", "msg": "Sign-off required for pull request"}
}
