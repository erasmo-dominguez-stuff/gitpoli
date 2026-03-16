"""Shared utilities used across router modules.

Keeps common response-formatting and audit-recording logic in one place
so each router only calls ``record_audit`` and gets a fully populated
response dict back.
"""

import logging

from fastapi import Request

from . import audit

logger = logging.getLogger(__name__)


def format_response(result: dict) -> dict:
    """Normalise an OPA result dict into ``{allow, violations}``.

    Violations are sorted by code so responses are deterministic and easy
    to compare in tests.
    """
    return {
        "allow": result.get("allow", False),
        "violations": sorted(
            result.get("violations", []), key=lambda v: v.get("code", "")
        ),
    }


def record_audit(
    policy: str,
    result: dict,
    input_data: dict,
    request: Request,
    source: str = "api",
) -> dict:
    """Format the OPA result, write an audit event, and return the combined response.

    Returns a dict with ``allow``, ``violations``, and ``audit_id`` keys.
    Routers can add extra fields (e.g. ``input``, ``check_run_posted``) before
    returning the dict to the caller.
    """
    resp = format_response(result)
    event = audit.record(
        policy=policy,
        decision=resp["allow"],
        violations=resp["violations"],
        input_data=input_data,
        actor=request.headers.get("X-Actor", ""),
        source=source,
    )
    resp["audit_id"] = event["id"]
    logger.info(
        "policy=%s decision=%s audit_id=%s",
        policy,
        event["decision"],
        event["id"],
    )
    return resp
