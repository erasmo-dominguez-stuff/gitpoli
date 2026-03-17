# Policy TDD Guide

- Write tests for new policy logic in this folder before implementing the policy.
- Use pytest for simple, readable assertions.
- Example: test minimum approvals, branch rules, sign-off, etc.
- Extract logic from tests to policy modules (handlers, rego, etc).

## Example

See `test_new_policy.py` for a template.
