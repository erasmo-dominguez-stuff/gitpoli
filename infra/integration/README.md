# Integration Environment

End-to-end testing with real GitHub webhooks. Runs the policy server locally and
receives GitHub `deployment_protection_rule` events via [smee.io](https://smee.io).

## Architecture

```
GitHub (deployment_protection_rule)
         │
         ▼
     smee.io channel
         │
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌──────────┐
│  smee-client    │────▶│  Policy Server  │────▶│   OPA    │
│  (alpine+node)  │     │  (FastAPI:8080) │     │  (:8181) │
└─────────────────┘     └────────┬────────┘     └──────────┘
                                 │
                         GitHub API callback
                         (approve / reject)
```

The server receives the webhook, evaluates the policy via OPA, records an
audit event, and calls back to GitHub's `deployment_callback_url` to
approve or reject the deployment.

## Prerequisites

- Docker + Docker Compose
- A GitHub repository with environments configured
- A GitHub App installed on the repo (with `deployment_protection_rule` event permission)

## Setup

```bash
# Run the interactive setup (creates smee channel if needed, validates credentials)
make integration-setup

# Or manually:
# 1. Copy .env.example → .env
# 2. Set SMEE_URL (or leave empty — the smee container auto-creates one)
# 3. Set GITHUB_APP_ID and place the .pem key at infra/integration/app.pem
```

Then configure your GitHub repository:

1. **Settings → Webhooks → Add webhook**
   - Payload URL: your smee.io channel URL
   - Content type: `application/json`
   - Events: select **Deployment protection rules**

2. **Settings → Environments → (select environment) → Deployment protection rules**
   - Enable the webhook-based custom protection rule

## Usage

```bash
# Start all services (OPA + server + smee tunnel)
make integration-up

# View logs
make integration-logs

# Trigger a deployment in your repo, then check the audit trail:
curl -s http://localhost:8080/audit | jq .

# Stop services
make integration-down
```

## How It Works

1. You trigger a deployment in your GitHub repository
2. GitHub sends a `deployment_protection_rule` event to the smee.io channel
3. `smee-client` forwards it to `POST /webhook` on the policy server
4. The server dispatches by `X-GitHub-Event` header to the deploy handler
5. The handler loads `.repol/deploy.yaml`, builds the OPA input, and queries OPA
6. OPA evaluates `policies/deploy.rego` and returns allow/deny + violations
7. The server records an audit event and calls back to GitHub to approve/reject

## Services

| Service | Port | Description |
|---------|------|-------------|
| `opa`    | 8181 | OPA REST API with policies mounted |
| `server` | 8080 | Policy evaluation server (FastAPI) |
| `smee`   | —    | Webhook tunnel (smee.io → server) |

## Troubleshooting

**smee not connecting:**
Check that `SMEE_URL` in `.env` points to a valid smee.io channel.

**GitHub callback failing:**
Verify that `GITHUB_APP_ID` is set and `app.pem` exists. The App must be
installed on the target repository. Check `make integration-logs` for
`GitHub callback` lines.

**smee auto-created a new URL:**
If `SMEE_URL` is empty, the smee container creates a new channel on startup.
Update the webhook URL in your GitHub repo settings to match the new one
shown in the logs (`make integration-logs`).

**Policy evaluation returning unexpected results:**
Test directly: `curl -s http://localhost:8080/evaluate/deploy -d @infra/local/payloads/deploy_valid.json | jq .`
