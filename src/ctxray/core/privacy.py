# src/ctxray/core/privacy.py
"""Privacy metadata registry for prompt sources.

Maps each adapter to a PrivacyProfile describing whether prompts are sent to the
cloud, how they are retained, and whether they may be used for model training.
Provides compute_privacy_summary() for aggregating privacy posture across sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PrivacyProfile:
    """Immutable privacy metadata for a single prompt source."""

    cloud: bool
    retention: str  # "none" | "transient" | "persistent" | "policy-dependent"
    training: str  # "never" | "opt-out" | "opt-in" | "unknown"
    note: str = field(default="")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ADAPTER_PRIVACY: dict[str, PrivacyProfile] = {
    "claude-code": PrivacyProfile(
        cloud=True,
        retention="policy-dependent",
        training="never",
    ),
    "cursor": PrivacyProfile(
        cloud=True,
        retention="transient",
        training="never",
    ),
    "openclaw": PrivacyProfile(
        cloud=True,
        retention="policy-dependent",
        training="unknown",
    ),
    "aider": PrivacyProfile(
        cloud=False,
        retention="none",
        training="never",
    ),
    "gemini": PrivacyProfile(
        cloud=True,
        retention="transient",
        training="opt-out",
    ),
    "cline": PrivacyProfile(
        cloud=True,
        retention="policy-dependent",
        training="unknown",
    ),
    "chatgpt-export": PrivacyProfile(
        cloud=True,
        retention="persistent",
        training="opt-out",
    ),
    "claude-chat-export": PrivacyProfile(
        cloud=True,
        retention="persistent",
        training="never",
    ),
}

_UNKNOWN_PROFILE = PrivacyProfile(
    cloud=True,
    retention="unknown",
    training="unknown",
)

# Training values considered "exposed" (not definitively safe)
_TRAINING_EXPOSED = {"opt-out", "opt-in", "unknown"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_profile(source: str) -> PrivacyProfile:
    """Look up the privacy profile for *source*, falling back to an unknown profile."""
    return ADAPTER_PRIVACY.get(source, _UNKNOWN_PROFILE)


def compute_privacy_summary(source_counts: dict[str, int]) -> dict[str, Any]:
    """Aggregate privacy posture across multiple prompt sources.

    Parameters
    ----------
    source_counts:
        Mapping of adapter name to prompt count, e.g. ``{"claude-code": 120}``.

    Returns
    -------
    dict with keys: total_prompts, cloud_prompts, local_prompts,
    training_exposed, training_safe, sources (list of per-source detail dicts
    sorted by count descending).
    """
    total = 0
    cloud = 0
    local = 0
    training_exposed = 0
    training_safe = 0
    sources: list[dict[str, Any]] = []

    for source, count in source_counts.items():
        profile = get_profile(source)
        total += count

        if profile.cloud:
            cloud += count
        else:
            local += count

        if profile.training in _TRAINING_EXPOSED:
            training_exposed += count
        else:
            training_safe += count

        sources.append(
            {
                "source": source,
                "count": count,
                "cloud": profile.cloud,
                "retention": profile.retention,
                "training": profile.training,
            }
        )

    sources.sort(key=lambda d: d["count"], reverse=True)

    return {
        "total_prompts": total,
        "cloud_prompts": cloud,
        "local_prompts": local,
        "training_exposed": training_exposed,
        "training_safe": training_safe,
        "sources": sources,
    }
