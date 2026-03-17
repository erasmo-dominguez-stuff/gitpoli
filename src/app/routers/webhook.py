"""GitHub webhook endpoints (extensible).

This module is the entry point for all GitHub App webhook events.
Responsibilities:
    1. Verify the HMAC-SHA256 signature that GitHub attaches to every request.
    2. Extract relevant fields from the raw webhook payload.
    3. Dispatch to explicit handler registry for normalization/evaluation.
    4. Call OPA to evaluate the policy.
    5. Post the result back to GitHub (Check Run for PRs, callback for deployments).

Extensibility:
    - Handlers for each event type are registered in src/app/handlers/.
    - To add a new policy, create a handler module and register it.

Routes:
    POST /webhook                           — main entry point (routes by X-GitHub-Event)
    POST /webhook/deployment_protection_rule — direct, for deployment events
    POST /webhook/pull_request              — direct, for PR opened/synchronize/etc.
    POST /webhook/pull_request_review       — direct, for review submitted/dismissed
"""
from ..handlers import get_handler

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

# ...existing code for helpers and endpoints...
