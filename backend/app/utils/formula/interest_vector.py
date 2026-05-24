"""
Interest Vector formula module — EMA (Exponential Moving Average) update logic.

Centralises the vector-update math so that services only orchestrate I/O
while this module owns all constants and pure computation.

Formula:
    new_vec = α * current_vec  +  (1 - α) * weight * video_embedding
    then L2-normalize for cosine similarity correctness.

References:
    - docs/interaction_api_design.md  §3 "User Interest Vector Update"
    - docs/interaction_flow_guide.md  §Bước 5
"""

import math
from typing import Dict, List

# ── Constants ──────────────────────────────────────────────────────

# EMA momentum: how much we preserve the existing vector.
# 0.85 = keep 85 % old, blend 15 % new signal.
EMA_MOMENTUM: float = 0.85

# Interaction-type weights for interest_vector updates.
# Positive → pull vector toward the video embedding.
# Negative → push vector away (e.g. skip).
INTERACTION_WEIGHTS: Dict[str, float] = {
    "like":    1.0,   # strong positive signal
    "replay":  0.8,   # rewatched — strong
    "comment": 0.6,   # engaged enough to comment
    "share":   0.5,   # positive but weaker signal
    "passive_view": 0.2, # positive but passive signal
    "skip":   -0.3,   # negative signal
}


# ── Pure Functions ─────────────────────────────────────────────────

def get_interaction_weight(interaction_type: str) -> float:
    """Return the vector-update weight for a given interaction type.

    Returns 0.0 for unknown types (neutral — no update).
    """
    return INTERACTION_WEIGHTS.get(interaction_type, 0.0)


def calculate_ema_vector(
    current_vec: List[float],
    video_vec: List[float],
    weight: float,
    momentum: float = EMA_MOMENTUM,
) -> List[float]:
    """Compute an EMA-blended interest vector and L2-normalize.

    Args:
        current_vec: The user's existing interest vector (N-dim).
        video_vec:   The video's embedding vector (N-dim, same length).
        weight:      Interaction weight (from INTERACTION_WEIGHTS).
        momentum:    How much of the old vector to preserve (default 0.85).

    Returns:
        A new L2-normalized vector of the same dimensionality.
    """
    α = momentum
    new_vec = [
        α * c + (1.0 - α) * weight * v
        for c, v in zip(current_vec, video_vec)
    ]

    # L2-normalize so cosine distance works correctly in $vectorSearch
    magnitude = math.sqrt(sum(x * x for x in new_vec))
    if magnitude > 0:
        new_vec = [x / magnitude for x in new_vec]

    return new_vec


def calculate_batch_ema_vector(
    current_vec: List[float],
    list_of_video_vecs: List[List[float]],
    list_of_weights: List[float],
    momentum: float = EMA_MOMENTUM,
) -> List[float]:
    """Compute an EMA-blended interest vector for a batch of interactions and L2-normalize.

    Args:
        current_vec: The user's existing interest vector (N-dim).
        list_of_video_vecs: List of video embedding vectors.
        list_of_weights: List of interaction weights.
        momentum: How much of the old vector to preserve (default 0.85).

    Returns:
        A new L2-normalized vector of the same dimensionality.
    """
    if not list_of_video_vecs or not list_of_weights:
        return current_vec

    vec_len = len(current_vec) if current_vec else len(list_of_video_vecs[0])
    session_vector = [0.0] * vec_len
    total_weight = sum(abs(w) for w in list_of_weights)

    if total_weight == 0:
        return current_vec

    for vec, weight in zip(list_of_video_vecs, list_of_weights):
        for i in range(len(vec)):
            session_vector[i] += vec[i] * weight

    session_vector = [x / total_weight for x in session_vector]

    if not current_vec:
        magnitude = math.sqrt(sum(x * x for x in session_vector))
        if magnitude > 0:
            return [x / magnitude for x in session_vector]
        return session_vector

    α = momentum
    new_vec = [
        α * c + (1.0 - α) * s
        for c, s in zip(current_vec, session_vector)
    ]

    magnitude = math.sqrt(sum(x * x for x in new_vec))
    if magnitude > 0:
        new_vec = [x / magnitude for x in new_vec]

    return new_vec
