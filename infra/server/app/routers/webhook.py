"""GitHub webhook endpoints.

This module is the entry point for all GitHub App webhook events.  Its
responsibility is to:

  1. Verify the HMAC-SHA256 signature that GitHub attaches to every request.
  2. Extract the relevant fields from the raw webhook payload.
  3. Translate the payload into the normalised OPA input format.
  4. Call OPA to evaluate the policy.
  5. Post the result back to GitHub (Check Run for PRs, callback for deployments).

Routes:
  POST /webhook                           — main entry point (routes by X-GitHub-Event)
  POST /webhook/deployment_protection_rule — direct, for deployment events
  POST /webhook/pull_request              — direct, for PR opened/synchronize/etc.
  POST /webhook/pull_request_review       — direct, for review submitted/dismissed
"""

import hashlib
import hmac
import json
import logging
import secrets

import yaml
from fastapi import APIRouter, HTTPException, Request

from ..config import PR_FORCE_APPROVERS, REPOL_DIR, WEBHOOK_SECRET
from ..github import get_pr_approvers, github_callback, github_check_run
from ..helpers import record_audit
from ..opa import query_opa

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


# ── Webhook-specific helpers ──────────────────────────────────────────────────


def _load_yaml(name: str) -> dict:
    """Load a YAML policy file from REPOL_DIR."""
    path = REPOL_DIR / name
    if not path.is_file():
        raise HTTPException(status_code=500, detail=f"Policy file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def _csv_header(request: Request, name: str) -> list[str]:
    """Parse a comma-separated header into a trimmed list."""
    raw = request.headers.get(name, "")
    return [v.strip() for v in raw.split(",") if v.strip()] if raw else []


def _bool_header(request: Request, name: str, default: bool = False) -> bool:
    """Parse a request header as a boolean (``"true"`` / ``"false"``).    """
    return request.headers.get(name, str(default)).lower() == "true"


def _int_header(request: Request, name: str, default: int = 0) -> int:
    """Parse a request header as an integer, returning *default* on failure."""
    try:
        return int(request.headers.get(name, str(default)))
    except ValueError:
        return default


async def _verify_signature(request: Request, raw_body: bytes) -> None:
    """Verify the HMAC-SHA256 signature that GitHub attaches to every webhook.

    GitHub signs the raw request body with the shared WEBHOOK_SECRET and
    puts the result in the ``X-Hub-Signature-256`` header.  We must validate
    this before processing the payload to prevent any unauthenticated caller
    from triggering policy evaluations or deployment callbacks.

    When WEBHOOK_SECRET is not configured the check is skipped with a warning.
    This is acceptable for local development but must never happen in production.

    Raises:
        HTTPException 401: When the header is missing or the signature does not match.
    """
    if not WEBHOOK_SECRET:
        logger.warning(
            "WEBHOOK_SECRET is not set — skipping signature verification. "
            "Set WEBHOOK_SECRET in production to prevent unauthenticated calls."
        )
        return

    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not sig_header:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    # secrets.compare_digest prevents timing-based side-channel attacks.
    if not secrets.compare_digest(expected, sig_header):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


# ── Dispatch (single entrypoint for real GitHub webhooks) ─────────────────────


@router.post("")
async def webhook_dispatch(request: Request) -> dict:
    """Route incoming GitHub webhooks by X-GitHub-Event header.

    This is the URL you configure in your GitHub App / smee-client.
    It validates the HMAC signature first, then delegates to the
    appropriate event handler based on event type and action.
    """
    # Read the raw body first so we can validate the HMAC signature before
    # deserialising.  FastAPI/Starlette caches request.body(), so subsequent
    # calls to request.json() will still work correctly.
    raw_body = await request.body()
    await _verify_signature(request, raw_body)

    body: dict = json.loads(raw_body)
    event_type: str = request.headers.get("X-GitHub-Event", "")
    action: str = body.get("action", "")
    logger.info("Received event=%s action=%s", event_type, action)

    if event_type == "deployment_protection_rule":
        return await _handle_deploy(request, body)
    if event_type == "deployment":
        return await _handle_deploy(request, body)
    if event_type == "pull_request" and action in {
        "opened", "synchronize", "reopened", "ready_for_review"
    }:
        return await _handle_pr(request, body)
    if event_type == "pull_request_review" and action in {"submitted", "dismissed"}:
        return await _handle_pr(request, body)

    # Acknowledge events we don't act on (ping, workflow_run, etc.)
    logger.debug("Ignored event=%s action=%s", event_type, action)
    return {"event": event_type, "action": "ignored"}


# ── Deployment protection rule ────────────────────────────────────────────────


@router.post("/deployment_protection_rule")
async def webhook_deploy(request: Request) -> dict:
    """Handle deployment_protection_rule event (direct endpoint)."""
    body = await request.json()
    return await _handle_deploy(request, body)


async def _handle_deploy(request: Request, event: dict) -> dict:
    """Core logic for deployment policy evaluation.

    Normalises two different GitHub event shapes into a single OPA input:
      - ``deployment_protection_rule``: has ``deployment.ref`` and
        ``deployment_callback_url`` — used for custom protection rules.
      - ``deployment``: has ``deployment.ref`` and ``deployment.environment``.

    Metadata not present in the webhook payload (approvers, test results, etc.)
    can be injected via request headers when calling the direct endpoint from CI:
      X-Approvers         — comma-separated logins
      X-Tests-Passed      — true / false
      X-Signed-Off        — true / false
      X-Deployments-Today — integer
    """
    deployment = event.get("deployment", {})
    environment = event.get("environment") or deployment.get("environment", "")
    ref = deployment.get("ref", "")
    if ref and not ref.startswith("refs/"):
        ref = f"refs/heads/{ref}"

    callback_url = event.get("deployment_callback_url", "")
    installation_id = (event.get("installation") or {}).get("id")

    repo_policy = _load_yaml("deploy.yaml")
    env_names = list(repo_policy.get("policy", {}).get("environments", {}).keys())

    opa_input = {
        "environment": environment,
        "ref": ref,
        "repo_environments": env_names,
        "workflow_meta": {
            "approvers": _csv_header(request, "X-Approvers"),
            "checks": {"tests": _bool_header(request, "X-Tests-Passed")},
            "signed_off": _bool_header(request, "X-Signed-Off"),
            "deployments_today": _int_header(request, "X-Deployments-Today"),
        },
        "repo_policy": repo_policy,
    }

    result = await query_opa("github/deploy", opa_input)
    resp = record_audit("deploy", result, opa_input, request, source="webhook")
    resp["input"] = opa_input

    if callback_url:
        await github_callback(
            callback_url,
            resp["allow"],
            resp["violations"],
            resp["audit_id"],
            environment_name=environment,
            installation_id=installation_id,
        )
        resp["callback_url"] = callback_url
        resp["callback_sent"] = True

    return resp


# ── Pull request ──────────────────────────────────────────────────────────────


@router.post("/pull_request")
async def webhook_pr(request: Request) -> dict:
    """Handle pull_request event (direct endpoint)."""
    body = await request.json()
    return await _handle_pr(request, body)


@router.post("/pull_request_review")
async def webhook_pr_review(request: Request) -> dict:
    """Handle pull_request_review event (direct endpoint).

    Triggered when a reviewer submits or dismisses a review.
    Re-evaluates the PR policy with the updated set of approvers and
    posts a fresh Check Run reflecting the current approval state.
    """
    body = await request.json()
    return await _handle_pr(request, body)


async def _resolve_pr_approvers(
    event: dict,
    request: Request,
    repo_full_name: str,
    pr_number: int,
    installation_id: int | None,
) -> list[str]:
    """Determine the current set of PR approvers for policy evaluation.

    Resolution is attempted in this order, stopping at the first success:

    1. **GitHub API** — when a GitHub App is configured and an
       ``installation_id`` is present in the payload, fetch all submitted
       reviews.  This is always the most accurate source because it reflects
       the full review history (including reviews from previous commits).

    2. **X-Approvers header** — an explicit comma-separated override useful
       for CI pipelines and local testing when no GitHub App is available.

    3. **Review payload** — last resort for the ``pull_request_review`` event.
       Only adds the reviewer when the submitted state is ``APPROVED``;
       ``changes_requested``, ``dismissed``, and ``commented`` purposely
       produce an empty list so a non-approval does not count as approval.

    After resolution, any logins in ``PR_FORCE_APPROVERS`` (integration-test
    helper) are merged in.
    """
    if installation_id and repo_full_name and pr_number:
        approvers = await get_pr_approvers(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
    elif header_approvers := _csv_header(request, "X-Approvers"):
        approvers = header_approvers
    else:
        review = event.get("review", {})
        if review.get("state", "").upper() == "APPROVED":
            login = review.get("user", {}).get("login", "")
            approvers = [login] if login else []
            logger.info("Approver extracted from review payload: %s", approvers)
        else:
            approvers = []

    if PR_FORCE_APPROVERS:
        approvers = list({*approvers, *PR_FORCE_APPROVERS})
        logger.info("PR_FORCE_APPROVERS active — merged approvers: %s", approvers)

    return approvers


async def _handle_pr(request: Request, event: dict) -> dict:
    """Core logic for pull request policy evaluation.

    Handles both ``pull_request`` and ``pull_request_review`` event shapes.
    Delegates approver resolution to ``_resolve_pr_approvers`` and posts a
    Check Run so the result appears directly on the PR on GitHub.
    """
    pr = event.get("pull_request", event)
    head_ref: str = pr.get("head", {}).get("ref", pr.get("head_ref", ""))
    base_ref: str = pr.get("base", {}).get("ref", pr.get("base_ref", ""))
    head_sha: str = pr.get("head", {}).get("sha", "")
    pr_number: int = pr.get("number", 0)
    repo_full_name: str = (event.get("repository") or {}).get("full_name", "")
    installation_id: int | None = (event.get("installation") or {}).get("id")

    approvers = await _resolve_pr_approvers(
        event=event,
        request=request,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        installation_id=installation_id,
    )

    repo_policy = _load_yaml("pullrequest.yaml")

    opa_input = {
        "head_ref": head_ref,
        "base_ref": base_ref,
        "workflow_meta": {
            "approvers": approvers,
            "signed_off": _bool_header(request, "X-Signed-Off"),
        },
        "repo_policy": repo_policy,
    }

    result = await query_opa("github/pullrequest", opa_input)
    resp = record_audit("pullrequest", result, opa_input, request, source="webhook")
    resp["input"] = opa_input

    if head_sha and repo_full_name:
        await github_check_run(
            repo_full_name=repo_full_name,
            head_sha=head_sha,
            allow=resp["allow"],
            violations=resp["violations"],
            audit_id=resp["audit_id"],
            installation_id=installation_id,
        )
        resp["check_run_posted"] = True

    return resp
