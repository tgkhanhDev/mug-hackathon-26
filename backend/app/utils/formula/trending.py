"""
Trending Score formula module — time-decay, velocity, and MongoDB pipeline helpers.

Centralises every trending-related constant, the decay math, and the
MongoDB aggregation-pipeline snippets so they are defined in exactly
one place across the whole codebase.
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

# ── Constants ──────────────────────────────────────────────────────

# Weights for the raw trending-score formula:
#   trending_score = view_count * W_view + like_count * W_like + comment_count * W_comment
TRENDING_WEIGHTS: Dict[str, int] = {
    "view":    1,
    "like":    3,
    "comment": 5,
}

# Time-decay half-life in hours, per video category
HALF_LIFE_HOURS: Dict[str, float] = {
    "entertainment": 168.0,   # 7 days
    "sports":        120.0,   # 5 days
    "gaming":        168.0,   # 7 days
    "lifestyle":     336.0,   # 14 days
    "education":     720.0,   # 30 days
    "calming":       720.0,   # 30 days
    "nature":        720.0,   # 30 days
    "cooking":       336.0,   # 14 days
    "_default":      168.0,   # 7 days fallback
}

# Minimum views/day for a video to still be considered "trending"
MIN_VELOCITY_VIEWS_PER_DAY = 10


# ── Pure Functions ─────────────────────────────────────────────────

def calculate_raw_trending_score(
    view_count: int,
    like_count: int,
    comment_count: int,
) -> float:
    """Compute the raw (non-decayed) trending score in Python.

    Formula: view_count * 1 + like_count * 3 + comment_count * 5
    """
    return (
        view_count  * TRENDING_WEIGHTS["view"]
        + like_count  * TRENDING_WEIGHTS["like"]
        + comment_count * TRENDING_WEIGHTS["comment"]
    )


def calculate_time_decay_metrics(
    now: datetime,
    created_at: datetime,
    category: str,
    raw_score: float,
    view_count: int,
    snapshot_at: Optional[datetime] = None,
    snapshot_views: Optional[int] = None,
    window_days: int = 7
) -> Dict[str, Any]:
    """
    Calculates time-decay score and trending status for a video.
    Returns a dict with calculated metrics.
    """
    age_hours = max(0.0, (now - created_at).total_seconds() / 3600)

    half_life = HALF_LIFE_HOURS.get(category, HALF_LIFE_HOURS["_default"])
    
    # Decay constant λ = ln(2) / half_life
    lam = math.log(2) / half_life
    decay_factor = math.exp(-lam * age_hours)
    effective_score = raw_score * decay_factor

    # Velocity check
    if snapshot_at and snapshot_views is not None:
        elapsed_days = max(
            0.01,
            (now - snapshot_at).total_seconds() / 86400,
        )
        velocity_7d = (view_count - snapshot_views) / elapsed_days
    elif age_hours > 0:
        velocity_7d = view_count / (age_hours / 24)
    else:
        velocity_7d = float(view_count)

    # Is trending check
    is_trending = (
        velocity_7d >= MIN_VELOCITY_VIEWS_PER_DAY
        and age_hours <= window_days * 24 * 4  # generous 4x window
    )

    return {
        "effective_score": round(effective_score, 2),
        "age_hours": round(age_hours, 1),
        "decay_factor": round(decay_factor, 4),
        "velocity_7d": round(velocity_7d, 1),
        "is_trending": is_trending,
    }


# ── MongoDB Pipeline Builders ─────────────────────────────────────

def build_trending_score_pipeline_stage() -> Dict[str, Any]:
    """Return a ``$addFields`` stage that computes ``trending_score`` dynamically.

    Usage (in any aggregation pipeline)::

        pipeline = [
            # ... other stages ...
            build_trending_score_pipeline_stage(),
            {"$sort": {"trending_score": -1}},
        ]
    """
    w = TRENDING_WEIGHTS
    return {
        "$addFields": {
            "trending_score": {
                "$add": [
                    {"$multiply": [{"$ifNull": ["$view_count", 0]}, w["view"]]},
                    {"$multiply": [{"$ifNull": ["$like_count", 0]}, w["like"]]},
                    {"$multiply": [{"$ifNull": ["$comment_count", 0]}, w["comment"]]},
                ]
            }
        }
    }


def build_trending_score_update_pipeline(inc_payload: Dict[str, int]) -> List[Dict[str, Any]]:
    """Return an aggregation-pipeline update for ``update_one`` that atomically
    increments counters and recalculates ``trending_score``.

    Args:
        inc_payload: Dict mapping counter field names to their increment deltas,
                     e.g. ``{"view_count": 1, "like_count": 1}``.

    Returns:
        A list of pipeline stages suitable for
        ``collection.update_one(filter, pipeline)``.
    """
    w = TRENDING_WEIGHTS

    # Build $set expressions for each counter: current + delta
    set_fields: Dict[str, Any] = {"updated_at": "$$NOW"}
    for field in ("view_count", "like_count", "comment_count"):
        delta = inc_payload.get(field, 0)
        set_fields[field] = {"$add": [{"$ifNull": [f"${field}", 0]}, delta]}

    return [
        {"$set": set_fields},
        {
            "$set": {
                "trending_score": {
                    "$add": [
                        {"$multiply": [{"$ifNull": ["$view_count", 0]}, w["view"]]},
                        {"$multiply": [{"$ifNull": ["$like_count", 0]}, w["like"]]},
                        {"$multiply": [{"$ifNull": ["$comment_count", 0]}, w["comment"]]},
                    ]
                }
            }
        },
    ]
