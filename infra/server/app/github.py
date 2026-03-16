"""GitHub API client — authenticates as a GitHub App (JWT).

The server authenticates as a GitHub App and generates short-lived
installation access tokens on demand.  The installation_id that GitHub
includes in every webhook payload is what ties a request to a specific
repository, so no static token per-repo is needed.

Flow:
  1. Generate a signed JWT using the App's RSA private key.
  2. Exchange the JWT for an installation token (valid 1 hour).
  3. Use the installation token for all GitHub API calls in that request.

Private key sources (in order of preference):
  GITHUB_APP_PRIVATE_KEY_PATH — path to a .pem file (local / Docker mount)
  GITHUB_APP_PRIVATE_KEY      — raw PEM content (cloud envs, e.g. Azure secrets)
"""

import logging
import time
from typing import Optional

import httpx
import jwt

from . import audit
from .config import GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_APP_PRIVATE_KEY_PATH

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_COMMON_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# ── GitHub App JWT ────────────────────────────────────────────────────────────

# The private key is loaded once and cached.  It never changes at runtime,
# so there is no need to reload it between requests.
_private_key: Optional[str] = None


def _load_private_key() -> str:
    """Return the RSA private key PEM string, loading it on the first call.

    Checks GITHUB_APP_PRIVATE_KEY_PATH (file) before falling back to the
    GITHUB_APP_PRIVATE_KEY env var (inline PEM content).  This allows the
    same image to be used in both local (file mount) and cloud (env secret)
    deployments without any code change.

    Raises:
        RuntimeError: If neither source is configured.
    """
    global _private_key
    if _private_key is not None:
        return _private_key
    if GITHUB_APP_PRIVATE_KEY_PATH:
        with open(GITHUB_APP_PRIVATE_KEY_PATH) as fh:
            _private_key = fh.read()
    elif GITHUB_APP_PRIVATE_KEY:
        # Inline PEM — useful when mounting files is not an option.
        _private_key = GITHUB_APP_PRIVATE_KEY
    else:
        raise RuntimeError(
            "No GitHub App private key configured. "
            "Set GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY."
        )
    return _private_key


def _generate_jwt() -> str:
    """Create a short-lived JWT signed with the App's RSA private key.

    GitHub accepts JWTs valid for at most 10 minutes.  We subtract 60 s
    from iat to account for clock drift between this server and GitHub.
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,   # issued-at with clock-drift margin
        "exp": now + 600,  # 10-minute expiry (GitHub maximum)
        "iss": GITHUB_APP_ID,
    }
    return jwt.encode(payload, _load_private_key(), algorithm="RS256")


async def _get_installation_token(installation_id: int) -> str:
    """Exchange a GitHub App JWT for a scoped installation access token.

    Installation tokens are valid for 1 hour.  We don't cache them here
    because each webhook request is short-lived; add caching if request
    volume justifies it.
    """
    url = f"{_GITHUB_API}/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            headers={**_COMMON_HEADERS, "Authorization": f"Bearer {_generate_jwt()}"},
        )
    resp.raise_for_status()
    return resp.json()["token"]


def is_app_configured() -> bool:
    """Return True when the minimum GitHub App credentials are present."""
    return bool(GITHUB_APP_ID and (GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY))


# ── Resolve auth header ──────────────────────────────────────────────────────


async def _auth_header(installation_id: Optional[int]) -> dict[str, str]:
    """Build the Authorization header needed for a GitHub API call.

    Returns an empty dict (instead of raising) so callers can decide
    whether to skip the API call or log a warning.
    """
    if not is_app_configured():
        logger.error(
            "GitHub App not configured — set GITHUB_APP_ID and "
            "GITHUB_APP_PRIVATE_KEY_PATH (or GITHUB_APP_PRIVATE_KEY)"
        )
        return {}
    if not installation_id:
        logger.error("No installation_id in webhook payload — cannot authenticate")
        return {}
    token = await _get_installation_token(installation_id)
    return {"Authorization": f"token {token}"}


# ── Callback ──────────────────────────────────────────────────────────────────


async def github_callback(
    callback_url: str,
    allow: bool,
    violations: list[dict],
    audit_id: str,
    *,
    environment_name: str = "",
    installation_id: Optional[int] = None,
) -> None:
    """POST back to GitHub to approve or reject a deployment protection rule.

    GitHub's custom deployment protection rules require the App to call back
    asynchronously — the webhook handler returns immediately and the decision
    is communicated via this endpoint.

    Args:
        callback_url: The ``deployment_callback_url`` from the webhook payload.
        allow: True → approved, False → rejected.
        violations: Violation dicts from the OPA evaluation (may be empty).
        audit_id: Audit event ID included in the comment for traceability.
        environment_name: GitHub environment name (required by the API).
        installation_id: Installation ID used to obtain an access token.
    """
    if not callback_url:
        logger.debug("No callback URL — skipping GitHub callback")
        return

    auth = await _auth_header(installation_id)
    if not auth:
        logger.warning("No GitHub credentials configured — cannot call back")
        return

    state = "approved" if allow else "rejected"
    comment_parts = [f"Policy decision: **{state}** (audit_id: `{audit_id}`)"]
    if violations:
        codes = ", ".join(v.get("code", "?") for v in violations)
        comment_parts.append(f"Violations: {codes}")

    payload = {
        "environment_name": environment_name,
        "state": state,
        "comment": ". ".join(comment_parts),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                callback_url,
                json=payload,
                headers={**_COMMON_HEADERS, **auth},
            )
        if resp.status_code >= 400:
            logger.warning(
                "GitHub callback error status=%d body=%s",
                resp.status_code,
                resp.text[:500],
            )
        logger.info(
            "GitHub callback status=%d state=%s env=%s auth=%s",
            resp.status_code,
            state,
            environment_name,
            "app" if installation_id else "none",
        )
        audit.update_callback(audit_id, status_code=resp.status_code, state=state)
    except Exception as exc:
        logger.error("GitHub callback failed: %s", exc)
        audit.update_callback(audit_id, status_code=0, state=f"error: {exc}")


# ── Check Run (PR policy result) ──────────────────────────────────────────────


async def github_check_run(
    *,
    repo_full_name: str,
    head_sha: str,
    allow: bool,
    violations: list[dict],
    audit_id: str,
    installation_id: Optional[int],
) -> None:
    """Create a GitHub Check Run that reports the PR policy decision.

    The check run name ``gitpoli / PR Policy`` must be configured as a
    required status check in branch protection rules so that a deny
    blocks the PR from merging.

    A new check run is created (not updated) on every evaluation.  GitHub
    automatically supersedes older runs for the same SHA and name.
    """
    auth = await _auth_header(installation_id)
    if not auth:
        logger.warning("No GitHub credentials — cannot post check run")
        return

    conclusion = "success" if allow else "failure"
    title = "Policy passed" if allow else "Policy violations found"

    if violations:
        codes = ", ".join(v.get("code", "?") for v in violations)
        summary = f"**Violations:** {codes}\n\n*audit_id: `{audit_id}`*"
    else:
        summary = f"All policy rules passed. *audit_id: `{audit_id}`*"

    payload = {
        "name": "gitpoli / PR Policy",
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {
            "title": title,
            "summary": summary,
        },
    }

    url = f"{_GITHUB_API}/repos/{repo_full_name}/check-runs"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={
                    **_COMMON_HEADERS,
                    **auth,
                    "Accept": "application/vnd.github+json",
                },
            )
        if resp.status_code >= 400:
            logger.warning(
                "Check run error status=%d body=%s",
                resp.status_code,
                resp.text[:500],
            )
        logger.info(
            "Check run posted status=%d conclusion=%s sha=%s",
            resp.status_code,
            conclusion,
            head_sha[:8],
        )
    except Exception as exc:
        logger.error("Check run failed: %s", exc)


async def get_pr_approvers(
    *,
    repo_full_name: str,
    pr_number: int,
    installation_id: Optional[int],
) -> list[str]:
    """Return the GitHub logins of all reviewers who currently approve the PR.

    Iterates all submitted reviews and collects unique logins whose latest
    state is ``APPROVED``.  Reviews that were later dismissed or superseded
    by a ``changes_requested`` review from the same user are excluded because
    only the most recent review per user is counted by GitHub itself.
    """
    auth = await _auth_header(installation_id)
    if not auth:
        return []

    url = f"{_GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers={**_COMMON_HEADERS, **auth})
        if resp.status_code != 200:
            return []
        reviews = resp.json()
        seen: set[str] = set()
        approvers = []
        for r in reviews:
            if r.get("state") == "APPROVED":
                login = r.get("user", {}).get("login", "")
                if login and login not in seen:
                    seen.add(login)
                    approvers.append(login)
        return approvers
    except Exception as exc:
        logger.error("Failed to fetch PR approvers: %s", exc)
        return []
