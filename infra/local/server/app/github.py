"""GitHub API client for deployment protection rule callbacks."""

import logging

import httpx

from .config import GITHUB_TOKEN

logger = logging.getLogger("policy-server")


async def github_callback(
    callback_url: str,
    allow: bool,
    violations: list,
    audit_id: str,
):
    """POST back to GitHub deployment_callback_url to approve/reject.

    GitHub custom deployment protection rules require the app to call back
    asynchronously to signal the decision.
    Docs: https://docs.github.com/en/actions/deployment/protecting-deployments
    """
    if not callback_url:
        logger.debug("No callback URL — skipping GitHub callback")
        return

    if not GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN not set — cannot call back to GitHub")
        return

    state = "approved" if allow else "rejected"
    comment_parts = [f"Policy decision: **{state}** (audit_id: `{audit_id}`)"]
    if violations:
        codes = ", ".join(v.get("code", "?") for v in violations)
        comment_parts.append(f"Violations: {codes}")

    payload = {
        "environment_name": "",
        "state": state,
        "comment": ". ".join(comment_parts),
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                callback_url,
                json=payload,
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        logger.info(
            "GitHub callback status=%d url=%s state=%s",
            resp.status_code,
            callback_url,
            state,
        )
    except Exception as exc:
        logger.error("GitHub callback failed: %s", exc)
