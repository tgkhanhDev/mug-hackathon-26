"""
Formula package — single source of truth for all algorithmic constants
and pure computation used by the Gotouchgrass recommendation engine.

Sub-modules:
    trending         — time-decay scoring, velocity, MongoDB pipeline helpers
    interest_vector  — EMA vector update, interaction weights
    fatigue          — mental-fatigue penalties, adaptive state machine
"""

from app.utils.formula.trending import (  # noqa: F401
    calculate_time_decay_metrics,
    calculate_raw_trending_score,
    build_trending_score_pipeline_stage,
    build_trending_score_update_pipeline,
    HALF_LIFE_HOURS,
    MIN_VELOCITY_VIEWS_PER_DAY,
    TRENDING_WEIGHTS,
)

from app.utils.formula.interest_vector import (  # noqa: F401
    calculate_ema_vector,
    calculate_batch_ema_vector,
    get_interaction_weight,
    EMA_MOMENTUM,
    INTERACTION_WEIGHTS,
)

from app.utils.formula.fatigue import (  # noqa: F401
    calculate_log_penalty,
    calculate_fatigue_score,
    determine_adaptive_state,
    FATIGUE_NORMAL_THRESHOLD,
    FATIGUE_WARNING_THRESHOLD,
)
