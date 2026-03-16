"""Audit trail query endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def get_audit(
    limit: int = Query(50, ge=1, le=500),
    policy: Optional[str] = Query(None),
    decision: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO timestamp"),
    environment: Optional[str] = Query(None),
):
    """Query audit events with optional filters."""
    return audit.query(
        limit=limit,
        policy=policy,
        decision=decision,
        since=since,
        environment=environment,
    )


@router.get("/summary")
async def get_audit_summary():
    """Aggregate stats: totals by decision, policy, and environment."""
    return audit.summary()


@router.get("/{event_id}")
async def get_audit_event(event_id: str):
    """Retrieve a single audit event by ID."""
    event = audit.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return event
