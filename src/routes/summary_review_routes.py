"""Summary & Review API endpoints for AI analysis and chat.

Provides REST API endpoints for multi-persona AI review generation
and follow-up chat functionality:
  POST /api/summary/ai-review - Generate multi-persona AI analysis
  POST /api/summary/chat - Send follow-up chat message

Validates Requirements: 8.1, 8.2, 8.4, 8.6
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.ai_chat_message import AIChatMessage
from src.models.ai_review_session import AIReviewSession
from src.schemas.summary_review import (
    ChatRequest,
    ChatResponse,
    GenerateReviewRequest,
    GenerateReviewResponse,
    MultiPersonaResult,
)
from src.services.summary_review_service import SummaryReviewService

logger = logging.getLogger(__name__)

# Create router with prefix
router = APIRouter(prefix="/api/summary", tags=["Summary & Review"])

# Ollama configuration from environment (same pattern as LLMAuditor)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


def _extract_flight_info(aggregated_summary: dict) -> tuple[str | None, str | None]:
    """Extract flight_number and flight_date from aggregated_summary.

    Looks in the flightPlan section of the aggregated summary for
    flight identifiers.

    Args:
        aggregated_summary: The aggregated summary from wizard steps 1-4.

    Returns:
        Tuple of (flight_number, flight_date) or (None, None) if not found.
    """
    flight_plan = aggregated_summary.get("flightPlan", {})
    flight_number = flight_plan.get("flight_number")
    flight_date = flight_plan.get("flight_date")
    return flight_number, flight_date


def _parse_flight_date(date_str: str | None):
    """Parse a date string into a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format or None.

    Returns:
        Parsed date object or None if parsing fails.
    """
    if not date_str:
        return None
    try:
        from datetime import date
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.warning("Invalid flight_date format: %s", date_str)
        return None


@router.post("/ai-review", response_model=GenerateReviewResponse, status_code=status.HTTP_200_OK)
async def generate_ai_review(
    request: GenerateReviewRequest,
    db: Session = Depends(get_db),
) -> GenerateReviewResponse:
    """Generate multi-persona AI analysis for overflight charge data.

    Creates a new AI review session, calls the SummaryReviewService to
    generate multi-persona analysis via Ollama, persists the session
    data to the database, and returns the results.

    Database write failures are handled gracefully: the AI results are
    still returned to the user even if persistence fails.

    Validates Requirements: 8.1, 8.2, 8.6

    Args:
        request: GenerateReviewRequest with aggregated_summary, charge_comparison,
                 compliance_enabled flag, and optional regenerate flag.
        db: Database session (injected).

    Returns:
        GenerateReviewResponse with session_id and multi_persona_result.
    """
    # Generate new session_id
    session_id = uuid.uuid4()

    # Extract calculation_id from aggregated_summary (required)
    route_cost_result = request.aggregated_summary.get("routeCostResult", {})
    calculation_id_str = route_cost_result.get("calculation_id")

    if not calculation_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing calculation_id in aggregated_summary.routeCostResult",
        )

    try:
        calculation_id = uuid.UUID(calculation_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid calculation_id format: {calculation_id_str}",
        )

    # Extract flight info for indexed lookups
    flight_number, flight_date_str = _extract_flight_info(request.aggregated_summary)
    flight_date = _parse_flight_date(flight_date_str)

    # Create initial session record (pending state)
    session_record = AIReviewSession(
        session_id=session_id,
        calculation_id=calculation_id,
        flight_number=flight_number,
        flight_date=flight_date,
        aggregated_summary=request.aggregated_summary,
        charge_comparison=request.charge_comparison,
        persona_prompts={},  # Will be updated after AI call
        raw_responses={},    # Will be updated after AI call
        multi_persona_result={},  # Will be updated after AI call
    )

    # Try to persist initial record
    db_write_failed = False
    try:
        db.add(session_record)
        db.flush()  # Get the record into the session without committing
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to create initial AI review session record: %s",
            str(e),
            exc_info=True,
        )
        db_write_failed = True

    # Call SummaryReviewService to generate AI analysis
    service = SummaryReviewService(ollama_url=OLLAMA_URL, model=OLLAMA_MODEL)

    try:
        result = await service.generate_review(
            aggregated_summary=request.aggregated_summary,
            charge_comparison=request.charge_comparison,
            compliance_enabled=request.compliance_enabled,
            regenerate=request.regenerate,
        )
    except Exception as e:
        logger.error(
            "AI review generation failed: %s",
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI review generation failed: {str(e)}",
        )

    # Update session record with results
    if not db_write_failed:
        try:
            session_record.persona_prompts = result.get("prompts", {})
            session_record.raw_responses = result.get("raw_responses", {})
            session_record.multi_persona_result = result.get("multi_persona_result", {})
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to update AI review session with results: %s",
                str(e),
                exc_info=True,
            )
            # Don't fail the request — still return AI results to user

    # Build response
    multi_persona_result = MultiPersonaResult(**result["multi_persona_result"])

    logger.info(
        "AI review generated successfully",
        extra={
            "session_id": str(session_id),
            "calculation_id": str(calculation_id),
            "compliance_enabled": request.compliance_enabled,
            "regenerate": request.regenerate,
        },
    )

    return GenerateReviewResponse(
        session_id=str(session_id),
        multi_persona_result=multi_persona_result,
    )


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def send_chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Send a follow-up chat message and get AI response.

    Validates the session_id exists, retrieves session context and chat
    history from the database, calls SummaryReviewService to get AI
    response, persists both user and assistant messages, and returns
    the assistant's response.

    Database write failures are handled gracefully: the chat response
    is still returned to the user even if persistence fails.

    Validates Requirements: 8.4, 8.6

    Args:
        request: ChatRequest with session_id and user message.
        db: Database session (injected).

    Returns:
        ChatResponse with assistant's response message.
    """
    # Validate session_id format
    try:
        session_uuid = uuid.UUID(request.session_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid session_id format: {request.session_id}",
        )

    # Retrieve session from database
    session_record = (
        db.query(AIReviewSession)
        .filter(AIReviewSession.session_id == session_uuid)
        .first()
    )

    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI review session found for session_id: {request.session_id}",
        )

    # Retrieve existing chat history for this session
    chat_messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.session_id == session_uuid)
        .order_by(AIChatMessage.created_at.asc())
        .all()
    )

    chat_history = [
        {"role": msg.role, "message": msg.message}
        for msg in chat_messages
    ]

    # Call SummaryReviewService to get AI response
    service = SummaryReviewService(ollama_url=OLLAMA_URL, model=OLLAMA_MODEL)

    try:
        result = await service.send_chat_message(
            session_id=request.session_id,
            user_message=request.message,
            aggregated_summary=session_record.aggregated_summary,
            multi_persona_result=session_record.multi_persona_result,
            chat_history=chat_history,
        )
    except Exception as e:
        logger.error(
            "Chat message processing failed: %s",
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat message processing failed: {str(e)}",
        )

    # Generate message IDs
    user_message_id = uuid.uuid4()
    assistant_message_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Persist user message
    db_write_failed = False
    try:
        user_msg_record = AIChatMessage(
            message_id=user_message_id,
            session_id=session_uuid,
            role="user",
            message=request.message,
            prompt=None,
            created_at=now,
        )
        db.add(user_msg_record)
        db.flush()
    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to persist user chat message: %s",
            str(e),
            exc_info=True,
        )
        db_write_failed = True

    # Persist assistant message
    if not db_write_failed:
        try:
            assistant_msg_record = AIChatMessage(
                message_id=assistant_message_id,
                session_id=session_uuid,
                role="assistant",
                message=result["message"],
                prompt=result.get("prompt"),
                created_at=now,
            )
            db.add(assistant_msg_record)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                "Failed to persist assistant chat message: %s",
                str(e),
                exc_info=True,
            )
            # Don't fail the request — still return chat response to user

    logger.info(
        "Chat message processed successfully",
        extra={
            "session_id": request.session_id,
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
        },
    )

    return ChatResponse(
        message_id=str(assistant_message_id),
        role="assistant",
        message=result["message"],
        created_at=now.isoformat(),
    )
