"""Pydantic schemas for Summary & Review AI analysis endpoint.

Defines request/response schemas for multi-persona AI review generation
and follow-up chat functionality.

Validates Requirements: 3.6, 7.4
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class Finding(BaseModel):
    """Schema for a single AI analysis finding.

    Represents an issue or observation identified by an AI persona
    during the review of overflight charge data.

    Validates Requirements: 3.6
    """

    category: str = Field(
        ...,
        description="Category of the finding (e.g., 'overcharge', 'missing_invoice', 'compliance')",
    )
    severity: str = Field(
        ...,
        description="Severity level: 'high', 'medium', or 'low'",
    )
    description: str = Field(
        ...,
        description="Detailed description of the finding",
    )
    affected_firs: list[str] = Field(
        default_factory=list,
        description="List of FIR ICAO codes affected by this finding",
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity is one of the allowed values."""
        allowed = {"high", "medium", "low"}
        if v.lower() not in allowed:
            raise ValueError(f"severity must be one of: {', '.join(allowed)}")
        return v.lower()


class AIReviewResult(BaseModel):
    """Schema for a single AI persona's review result.

    Contains the structured analysis output from one AI persona,
    including risk assessment, findings, and recommendations.

    Validates Requirements: 3.6
    """

    persona_name: str = Field(
        ...,
        description="Name of the AI persona that produced this result",
    )
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Risk score between 0.0 (lowest) and 1.0 (highest)",
    )
    findings: list[Finding] = Field(
        default_factory=list,
        description="List of findings identified by this persona",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of actionable recommendations",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="List of data gaps or missing information identified",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI confidence score between 0.0 (lowest) and 1.0 (highest)",
    )
    raw_response: Optional[str] = Field(
        default=None,
        description="Raw AI response text when parsing fails",
    )

    @field_validator("risk_score")
    @classmethod
    def validate_risk_score(cls, v: float) -> float:
        """Validate risk_score is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("risk_score must be between 0.0 and 1.0")
        return v

    @field_validator("confidence_score")
    @classmethod
    def validate_confidence_score(cls, v: float) -> float:
        """Validate confidence_score is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence_score must be between 0.0 and 1.0")
        return v


class MultiPersonaResult(BaseModel):
    """Schema for combined multi-persona AI analysis results.

    Contains the AI review results from all executed personas:
    mandatory Overflight Charges Analyst and Cost Control Analyst,
    plus optional Compliance Officer.

    Validates Requirements: 3.6
    """

    overflight_charges_analyst: AIReviewResult = Field(
        ...,
        description="Analysis result from the Overflight Charges Analyst persona",
    )
    cost_control_analyst: AIReviewResult = Field(
        ...,
        description="Analysis result from the Cost Control Analyst persona",
    )
    compliance_officer: Optional[AIReviewResult] = Field(
        default=None,
        description="Analysis result from the Compliance Officer persona (optional)",
    )


class GenerateReviewRequest(BaseModel):
    """Request schema for generating AI review analysis.

    Contains the aggregated wizard data and configuration options
    for the multi-persona AI analysis.

    Validates Requirements: 3.6
    """

    aggregated_summary: dict = Field(
        ...,
        description="Complete aggregated summary from wizard steps 1-4",
    )
    charge_comparison: list[dict] = Field(
        ...,
        description="Per-FIR charge comparison data (planned vs invoiced)",
    )
    compliance_enabled: bool = Field(
        default=False,
        description="Whether to include Compliance Officer persona analysis",
    )
    regenerate: bool = Field(
        default=False,
        description="Whether this is a regeneration request for fresh analysis",
    )


class GenerateReviewResponse(BaseModel):
    """Response schema for AI review generation.

    Contains the session identifier and multi-persona analysis results.

    Validates Requirements: 3.6
    """

    session_id: str = Field(
        ...,
        description="Unique session identifier for this AI review",
    )
    multi_persona_result: MultiPersonaResult = Field(
        ...,
        description="Combined analysis results from all executed personas",
    )


class ChatRequest(BaseModel):
    """Request schema for follow-up chat messages.

    Contains the session context and user message for AI chat interaction.

    Validates Requirements: 7.4
    """

    session_id: str = Field(
        ...,
        description="Session identifier linking to the AI review session",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="User's chat message",
    )


class ChatResponse(BaseModel):
    """Response schema for chat messages.

    Contains the AI assistant's response to a user chat message.

    Validates Requirements: 7.4
    """

    message_id: str = Field(
        ...,
        description="Unique identifier for this chat message",
    )
    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'",
    )
    message: str = Field(
        ...,
        description="Chat message content",
    )
    created_at: str = Field(
        ...,
        description="Message creation timestamp in ISO 8601 format",
    )

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is either 'user' or 'assistant'."""
        allowed = {"user", "assistant"}
        if v.lower() not in allowed:
            raise ValueError(f"role must be one of: {', '.join(allowed)}")
        return v.lower()
