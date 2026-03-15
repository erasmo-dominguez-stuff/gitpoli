# Contributing to Governant

## Prerequisites

| Tool | Install |
|------|---------|
| [OPA](https://www.openpolicyagent.org/) ≥ 1.9 | `brew install opa` or `make install-opa` |
| Python ≥ 3.8 | system / pyenv |
| [pre-commit](https://pre-commit.com/) | `pip install pre-commit` |
| [yq](https://github.com/mikefarah/yq) (optional) | `brew install yq` — falls back to Python |

## Getting started

```bash
# Clone and enter the repo
git clone https://github.com/erasmo-dominguez-stuff/governant.git
cd governant

# Install Python deps (dev extras)
pip install -e ".[dev]"

# Activate pre-commit hooks
pre-commit install

# Run the full check suite
make lint test
```

## Project layout

```
.repol/              # Policy YAML configs (teams edit these)
  pullrequest.yaml   # PR validation rules + branch naming
  deploy.yaml        # Deployment protection rules per environment
policies/
  lib/helpers.rego   # Shared helper functions
  pullrequest.rego   # PR policy (Rego)
  deploy.rego        # Deploy policy (Rego)
  tests/             # OPA unit tests
schemas/             # JSON Schemas that validate .repol/ files
scripts/             # Utility scripts (validation, CI helpers)
```

## Development workflow

### 1. Write / edit policies

Policies live in `policies/` as Rego v1 files. Shared helpers go in `policies/lib/helpers.rego`.

### 2. Write tests

Tests live in `policies/tests/`. Run them with:

```bash
make test           # verbose
make test-coverage  # with coverage report
```

### 3. Edit policy configs

Team-facing YAML configurations live in `.repol/`. After editing, validate them against the JSON Schemas:

```bash
make validate-schemas
```

### 4. Run all checks

```bash
make lint    # opa check + opa fmt --fail + schema validation
```

### 5. Pre-commit hooks

Pre-commit runs automatically on `git commit`. To run manually:

```bash
pre-commit run --all-files
```

The hooks enforce:
- Rego syntax check (`opa check`)
- Rego formatting (`opa fmt`)
- YAML schema validation
- Trailing whitespace / EOF fixes
- YAML lint

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add rate limit rule to deploy policy
fix: correct glob matching for nested branches
test: add branch naming edge cases
docs: update CONTRIBUTING with pre-commit setup
chore: bump OPA to 1.10
```

## Branch naming

Follow the branch rules defined in `.repol/pullrequest.yaml`:

| Source | Target |
|--------|--------|
| `feature/*` | `develop`, `main` |
| `bugfix/*` | `develop`, `main` |
| `hotfix/*` | `main`, `release/*` |
| `release/*` | `main` |
| `develop` | `main` |

## Adding a new policy

1. Create `policies/<name>.rego` with package `github.<name>`
2. Import `data.lib.helpers` for shared functions
3. Add tests in `policies/tests/<name>_test.rego`
4. If the policy needs a config file, create `.repol/<name>.yaml` and a matching schema in `schemas/`
5. Update `scripts/validate_schema.sh` with the new mapping
6. Run `make lint test` to verify
