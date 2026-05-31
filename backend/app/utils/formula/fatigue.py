"""
Fatigue Score formula module — mental-fatigue detection engine.

Centralises every penalty constant, tier threshold, and the adaptive
state-machine so that the service layer only needs to fetch data and
call these pure functions.

References:
    - docs/interaction_flow_guide.md  §Bước 4
"""

from typing import List

# ── Penalty Constants ──────────────────────────────────────────────

# Watch-duration penalty tiers: (upper_bound_seconds, penalty_points)
# Evaluated top-to-bottom; first match wins.
WATCH_DURATION_TIERS = [
    (2.0,  30),   # < 2 s  → 30 pts (doom-scrolling signal)
    (5.0,  15),   # < 5 s  → 15 pts
    (15.0,  5),   # < 15 s →  5 pts
]
WATCH_DURATION_DEFAULT_PENALTY = 0  # ≥ 15 s → no penalty

# Swipe-speed penalty tiers: (lower_bound_px_per_sec, penalty_points)
# Evaluated top-to-bottom; first match wins.
SWIPE_SPEED_TIERS = [
    (800.0, 20),  # > 800 px/s → 20 pts (frantic scrolling)
    (400.0, 10),  # > 400 px/s → 10 pts
]
SWIPE_SPEED_DEFAULT_PENALTY = 0  # ≤ 400 px/s → no penalty

# Passive-scroll penalty (user watched without any interaction)
PASSIVE_PENALTY = 15

# Consecutive-same-topic penalty tiers: (min_count, penalty_points)
# Evaluated top-to-bottom; first match wins.
CONSECUTIVE_TOPIC_TIERS = [
    (5, 25),   # ≥ 5 consecutive same topic → 25 pts
    (3, 15),   # ≥ 3 consecutive same topic → 15 pts
]
CONSECUTIVE_TOPIC_DEFAULT_PENALTY = 0  # < 3 → no penalty

# Dopamine intensity multiplier
DOPAMINE_PENALTY_MULTIPLIER = 10.0

# ── Adaptive State Thresholds ──────────────────────────────────────

FATIGUE_NORMAL_THRESHOLD = 40.0    # score < 40  → "normal"
FATIGUE_WARNING_THRESHOLD = 70.0   # score ≤ 70  → "warning"
FATIGUE_CRITICAL_THRESHOLD = 80.0  # score ≤ 80  → "exhausted", > 80 → "critical"


# ── Pure Functions ─────────────────────────────────────────────────

def calculate_log_penalty(
    watch_duration: float,
    swipe_speed: float,
    is_interaction: bool,
    consecutive_same_topic: int,
) -> int:
    """Calculate the fatigue penalty points for a single behavior-log entry.

    Returns an integer penalty ≥ 0.
    """
    # 1. Watch-duration penalty
    duration_penalty = WATCH_DURATION_DEFAULT_PENALTY
    for upper_bound, penalty in WATCH_DURATION_TIERS:
        if watch_duration < upper_bound:
            duration_penalty = penalty
            break

    # 2. Swipe-speed penalty
    swipe_penalty = SWIPE_SPEED_DEFAULT_PENALTY
    for lower_bound, penalty in SWIPE_SPEED_TIERS:
        if swipe_speed > lower_bound:
            swipe_penalty = penalty
            break

    # 3. Passive-scroll penalty
    passive_penalty = PASSIVE_PENALTY if not is_interaction else 0

    # 4. Consecutive-topic penalty
    count = consecutive_same_topic + 1  # stored value is 0-based
    consecutive_penalty = CONSECUTIVE_TOPIC_DEFAULT_PENALTY
    for min_count, penalty in CONSECUTIVE_TOPIC_TIERS:
        if count >= min_count:
            consecutive_penalty = penalty
            break

    return duration_penalty + swipe_penalty + passive_penalty + consecutive_penalty


def calculate_fatigue_score(
    log_penalties: List[int],
    high_intensity_count: int,
    low_intensity_count: int,
    total_videos_watched: int = 0,
) -> float:
    """Compute the overall fatigue score from per-log penalties + dopamine ratio.

    Args:
        log_penalties:        Penalty points for each of the recent behavior logs.
        high_intensity_count: Number of high-intensity videos watched in session.
        low_intensity_count:  Number of low-intensity videos watched in session.
        total_videos_watched: Total number of videos watched in session.

    Returns:
        A float clamped to [0.0, 100.0].
    """
    if not log_penalties:
        return 0.0

    # Dampen the average score when there are very few logs (e.g., at the start of a session)
    # by dividing by at least 5 logs. This prevents a single scroll from causing a massive spike.
    avg_log_points = sum(log_penalties) / max(5, len(log_penalties))

    total_intensity = high_intensity_count + low_intensity_count
    dopamine_penalty = (
        DOPAMINE_PENALTY_MULTIPLIER * (high_intensity_count / total_intensity)
        if total_intensity > 0
        else 0.0
    )

    # ── SESSION-BASED ACCUMULATION ──────────────────────────────────
    # The more videos watched in the session, the higher the fatigue grows.
    # Accumulate 0.5 points per video watched.
    volume_penalty = total_videos_watched * 0.5

    return min(100.0, max(0.0, avg_log_points + dopamine_penalty + volume_penalty))


def determine_adaptive_state(fatigue_score: float) -> str:
    """Map a fatigue score to the adaptive-state label.

    Returns one of: ``"normal"``, ``"warning"``, ``"exhausted"``, ``"critical"``.
    """
    if fatigue_score < FATIGUE_NORMAL_THRESHOLD:
        return "normal"
    elif fatigue_score <= FATIGUE_WARNING_THRESHOLD:
        return "warning"
    elif fatigue_score <= FATIGUE_CRITICAL_THRESHOLD:
        return "exhausted"
    else:
        return "critical"
