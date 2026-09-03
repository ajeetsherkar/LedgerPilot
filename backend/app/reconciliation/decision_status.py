from enum import Enum


class DecisionStatus(str, Enum):
    """
    Final terminal outcomes for Session 10 reconciliation.

    These are the business-facing statuses produced after
    matching, AI reasoning, and deterministic verification.
    """

    AUTO_RESOLVED = "AUTO_RESOLVED"
    AI_SUGGESTED = "AI_SUGGESTED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
