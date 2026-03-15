# governant

**Governance as Code for GitHub repositories.**

governant gives platform and security teams a single place to define, test, and enforce deployment and pull-request rules across their GitHub repositories — all as versioned Rego policies evaluated by [Open Policy Agent](https://www.openpolicyagent.org/).

[![OPA](https://img.shields.io/badge/OPA-v1.x-blue?logo=openpolicyagent)](https://www.openpolicyagent.org/)
[![Rego v1](https://img.shields.io/badge/Rego-v1-4a90e2)](https://www.openpolicyagent.org/docs/latest/policy-language/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Policies

governant currently implements two policies:

| Policy | Package | Purpose |
|--------|---------|---------|
| **Deployment Protection** | `github.deploy` | Enforces rules when deploying to protected environments (approvals, branches, tickets, tests, sign-off, rate limit) |
| **Pull Request** | `github.pullrequest` | Enforces rules on pull requests before merge (approvals, allowed branches, sign-off) |

Both policies share common helper functions located in `policies/lib/helpers.rego`.

---

## Repository Layout

```
├── .repol/                      # Team policy YAML configuration
├── policies/
│   ├── deploy.rego              # Deployment protection policy
│   ├── pullrequest.rego         # Pull request policy
│   ├── github_env_protect_policy.json
│   ├── github_pull_request_policy.json
│   ├── lib/
│   │   └── helpers.rego         # Shared helper functions
│   └── tests/
│       ├── deploy_test.rego     # Deploy policy tests
│       └── pullrequest_test.rego
├── schemas/
│   ├── github_env_protect_schema.json
│   └── github_pull_request_schema.json
├── scripts/
│   ├── github-environment-protect-check.sh
│   ├── github-pull-request-check.sh
│   └── validate_schema.sh
├── poc/                         # PoC webhook server (Flask)
├── .github/
│   ├── actions/eval-policy/     # Composite action for CI
│   └── workflows/               # CI/CD workflows
├── Makefile
└── pyproject.toml
```

---

## Quick Start

### Prerequisites

- [OPA CLI](https://www.openpolicyagent.org/docs/latest/#running-opa) v1.x
- `jq` (for schema validation fallback)

### Validate & Test

```bash
# Check Rego syntax
opa check policies/

# Run all tests
opa test policies/ --ignore "*.json" -v

# Validate policy JSON configs against schemas
./scripts/validate_schema.sh

# Or use make
make lint    # check + fmt + schema validation
make test    # run all OPA tests
```

### Evaluate Policies Locally

```bash
# Deploy policy
make eval-deploy

# PR policy
make eval-pr
```

### Build OPA Bundle

```bash
make build
```

---

## How It Works

Each policy follows the same pattern:

1. **Team configuration** — A JSON file (e.g., `github_env_protect_policy.json`) declares per-environment rules: required approvals, allowed branches, ticket requirements, etc.
2. **Schema validation** — A JSON Schema validates the configuration structure.
3. **Rego evaluation** — The policy evaluates `input` against the configuration and produces `allow` (boolean) and `violations` (set of `{code, msg}` objects).

### Deployment Protection (`github.deploy`)

Checks performed:
- Input and policy schema validation
- Environment exists in repository
- Branch is in the allowed list
- Valid ticket reference (regex pattern)
- Minimum approvals met
- CI tests passed
- DCO sign-off present
- Daily deployment rate limit

### Pull Request (`github.pullrequest`)

Checks performed:
- Policy and environment exist
- Environment exists in repository (configurable)
- Branch is in the allowed list
- Minimum approvals met
- DCO sign-off present

---

## Contributing

```bash
make install      # Install Python dev dependencies
make install-opa  # Install OPA CLI (macOS)
make lint         # Run all linting checks
make test         # Run all OPA tests
```

---

MIT © 2025 Erasmo Domínguez
