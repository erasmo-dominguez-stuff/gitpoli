"""Pull request policy handler.

Handles normalization and evaluation for pull request and review events.
"""

from ..helpers import record_audit
from ..opa import query_opa
from ..config import PR_FORCE_APPROVERS
from ..github import get_pr_approvers, github_check_run
from ..handlers import register_handler

import logging

logger = logging.getLogger(__name__)

async def handle_pull_request(request, event):
    pr = event.get("pull_request", event)
    head_ref = pr.get("head", {}).get("ref", pr.get("head_ref", ""))
    base_ref = pr.get("base", {}).get("ref", pr.get("base_ref", ""))
    head_sha = pr.get("head", {}).get("sha", "")
    pr_number = pr.get("number", 0)
    repo_full_name = (event.get("repository") or {}).get("full_name", "")
    installation_id = (event.get("installation") or {}).get("id")

    # Approver resolution
    approvers = []
    if installation_id and repo_full_name and pr_number:
        approvers = await get_pr_approvers(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            installation_id=installation_id,
        )
    if PR_FORCE_APPROVERS:
        approvers = list({*approvers, *PR_FORCE_APPROVERS})
        logger.info("PR_FORCE_APPROVERS active — merged approvers: %s", approvers)

    repo_policy = request.app.state.repo_policy_pullrequest

    opa_input = {
        "head_ref": head_ref,
        "base_ref": base_ref,
        "workflow_meta": {
            "approvers": approvers,
            "signed_off": request.headers.get("X-Signed-Off", "false") == "true",
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

register_handler("pull_request", handle_pull_request)
register_handler("pull_request_review", handle_pull_request)
