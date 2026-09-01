from dataclasses import dataclass
from enum import Enum


class ConfidenceBucket(str, Enum):
    """
    Confidence routing buckets.

    HIGH:
        Candidate is sufficiently confident for automatic
        resolution.

    MEDIUM:
        Candidate is plausible but should be sent to AI
        reasoning.

    LOW:
        Confidence is insufficient and requires human review.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True)
class ConfidenceThresholds:
    """
    Configurable thresholds for confidence bucketing.

    These are development defaults only.
    Final values must be tuned against the development set.
    """

    high: float
    medium: float

    def __post_init__(self):
        if not 0.0 <= self.medium <= 1.0:
            raise ValueError(
                "medium threshold must be between 0.0 and 1.0"
            )

        if not 0.0 <= self.high <= 1.0:
            raise ValueError(
                "high threshold must be between 0.0 and 1.0"
            )

        if self.high < self.medium:
            raise ValueError(
                "high threshold cannot be lower than "
                "medium threshold"
            )


def classify_confidence(
    confidence: float,
    thresholds: ConfidenceThresholds,
) -> ConfidenceBucket:
    """
    Convert a confidence score into a routing bucket.

    Rules:

        confidence >= high
            -> HIGH

        confidence >= medium
            -> MEDIUM

        otherwise
            -> LOW

    Thresholds are supplied externally so they can be tuned
    later against the development set.
    """

    if not 0.0 <= confidence <= 1.0:
        raise ValueError(
            "confidence must be between 0.0 and 1.0"
        )

    if confidence >= thresholds.high:
        return ConfidenceBucket.HIGH

    if confidence >= thresholds.medium:
        return ConfidenceBucket.MEDIUM

    return ConfidenceBucket.LOW
