from pydantic import BaseModel, ConfigDict, Field


class AIReasoningResponse(BaseModel):
    """
    Strict schema for every AI reconciliation response.

    The response must contain exactly:
        - classification
        - recommended_action
        - reason
        - confidence

    Confidence must be between 0.0 and 1.0.
    """

    model_config = ConfigDict(extra="forbid")

    classification: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
