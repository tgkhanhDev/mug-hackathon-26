"""
Scheduler controller — API to manage the embedding generation job.

Allows modifying the schedule interval at runtime via API instead of code changes.
"""

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.utils.scheduler import (
    get_schedule_info,
    update_schedule_interval,
    trigger_embedding_job_now,
)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


# ── Response Models ────────────────────────────────────────────
class ScheduleInfoResponse(BaseModel):
    job_id: str
    next_run_time: str | None
    is_running: bool


class ScheduleUpdateResponse(BaseModel):
    job_id: str
    interval_minutes: int
    message: str


class TriggerResponse(BaseModel):
    message: str


# ── Endpoints ──────────────────────────────────────────────────

@router.get(
    "/embedding",
    response_model=ScheduleInfoResponse,
    summary="Get embedding job status",
    description="Check the current status and next run time of the embedding generation job.",
)
async def get_embedding_schedule():
    """GET /api/v1/scheduler/embedding — Get schedule info."""
    return get_schedule_info()


@router.put(
    "/embedding",
    response_model=ScheduleUpdateResponse,
    summary="Update embedding job interval",
    description="Change the interval (in minutes) of the embedding generation job at runtime. "
    "No code changes or restart required.",
)
async def update_embedding_schedule(
    interval_minutes: int = Query(
        ..., ge=1, le=1440, description="New interval in minutes (1 min to 24 hours)"
    ),
):
    """PUT /api/v1/scheduler/embedding?interval_minutes=30 — Update interval."""
    return update_schedule_interval(interval_minutes)


@router.post(
    "/embedding/trigger",
    response_model=TriggerResponse,
    summary="Trigger embedding job now",
    description="Manually trigger the embedding generation job immediately, "
    "without waiting for the next scheduled run.",
)
async def trigger_embedding():
    """POST /api/v1/scheduler/embedding/trigger — Run job now."""
    return await trigger_embedding_job_now()
