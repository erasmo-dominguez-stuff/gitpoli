"""Deployment policy handler.

Handles normalization and evaluation for deployment and protection rule events.
"""

from ..helpers import record_audit
from ..opa import query_opa

from ..github import github_callback
from ..handlers import register_handler

import logging

logger = logging.getLogger(__name__)

async def handle_deploy(request, event):
    deployment = event.get("deployment", {})
    environment = event.get("environment") or deployment.get("environment", "")
    ref = deployment.get("ref", "")
    if ref and not ref.startswith("refs/"):
        ref = f"refs/heads/{ref}"

    callback_url = event.get("deployment_callback_url", "")
    installation_id = (event.get("installation") or {}).get("id")

    repo_policy = request.app.state.repo_policy_deploy
    env_names = list(repo_policy.get("policy", {}).get("environments", {}).keys())

    opa_input = {
        "environment": environment,
        "ref": ref,
        "repo_environments": env_names,
        "workflow_meta": {
            "approvers": request.headers.get("X-Approvers", "").split(","),
            "checks": {"tests": request.headers.get("X-Tests-Passed", "false") == "true"},
            "signed_off": request.headers.get("X-Signed-Off", "false") == "true",
            "deployments_today": int(request.headers.get("X-Deployments-Today", "0")),
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

register_handler("deployment_protection_rule", handle_deploy)
