"""Invoice Search API endpoint.

Provides a search endpoint for querying the invoices and fir_entries tables
with flexible criteria and FIR match confidence scoring.

POST /api/invoices/search — Search invoices by FIR codes and flight criteria.

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10,
                        1.11, 1.12, 1.13, 1.14, 1.15, 10.1, 10.3
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.invoice import FIREntry, Invoice
from src.schemas.invoice_search import (
    FIREntryResponse,
    InvoiceRecordResponse,
    InvoiceSearchRequest,
    InvoiceSearchResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/invoices", tags=["Invoice Search"])

# Maximum number of results to return per search
MAX_RESULTS = 100

# FIR match score sort order: strong first, then moderate, then none
_SCORE_ORDER = {"strong": 0, "moderate": 1, "none": 2}


def _parse_date(date_str: str) -> date:
    """Parse a YYYY-MM-DD string into a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        Parsed date object.

    Raises:
        HTTPException: If the date format is invalid.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Expected YYYY-MM-DD",
        )


def compute_fir_match_score(
    invoice_fir_codes: set[str], requested_fir_codes: set[str]
) -> str:
    """Compute FIR match score for an invoice against requested FIR codes.

    Classifies the match as:
    - "strong": more than half of the requested FIR codes appear in the invoice
    - "moderate": at least one but at most half of the requested codes match
    - "none": zero matches, or no requested FIR codes provided

    Validates Requirements: 1.11

    Args:
        invoice_fir_codes: Set of FIR codes from the invoice's fir_entries.
        requested_fir_codes: Set of FIR codes from the search request.

    Returns:
        "strong", "moderate", or "none".
    """
    if not requested_fir_codes:
        return "none"
    matched = invoice_fir_codes & requested_fir_codes
    ratio = len(matched) / len(requested_fir_codes)
    if ratio > 0.5:
        return "strong"
    elif len(matched) >= 1:
        return "moderate"
    return "none"


def _has_search_criteria(request: InvoiceSearchRequest) -> bool:
    """Check if at least one search criterion is provided.

    The fields aircraft_type, registration, origin, destination, and tenant_id
    are accepted for forward-compatibility but do not count as active search
    criteria since they are silently ignored (columns don't exist yet).

    Args:
        request: The search request to check.

    Returns:
        True if at least one active search criterion is provided.
    """
    return any([
        request.fir_codes,
        request.date_from,
        request.date_to,
        request.vendor,
        request.currency,
        request.min_amount is not None,
    ])


@router.post("/search", response_model=InvoiceSearchResponse)
async def search_invoices(
    request: InvoiceSearchRequest,
    db: Session = Depends(get_db),
) -> InvoiceSearchResponse:
    """Search invoices with flexible criteria and FIR match scoring.

    Accepts FIR codes, date range, vendor, currency, and min_amount filters.
    Returns matched invoices with their FIR entries and a computed
    fir_match_score, ordered by score descending then invoice_date descending,
    limited to 100 results.

    The fields aircraft_type, registration, origin, destination, and tenant_id
    are accepted but silently ignored until the corresponding database columns
    are added in a future migration.

    Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9,
                            1.10, 1.11, 1.12, 1.13, 1.14, 1.15, 10.1, 10.3

    Args:
        request: Search criteria with optional fields.
        db: Database session (injected).

    Returns:
        InvoiceSearchResponse with matched invoices and total count.

    Raises:
        HTTPException: 400 if no search criteria provided or dates are invalid.
        JSONResponse: 500 if a database error occurs.
    """
    # Validate at least one search criterion is provided
    if not _has_search_criteria(request):
        raise HTTPException(
            status_code=400,
            detail="At least one search criterion is required",
        )

    # Parse dates if provided
    date_from: date | None = None
    date_to: date | None = None
    if request.date_from:
        date_from = _parse_date(request.date_from)
    if request.date_to:
        date_to = _parse_date(request.date_to)

    # Build the set of requested FIR codes for scoring
    requested_fir_codes: set[str] = set()
    if request.fir_codes:
        requested_fir_codes = {code.upper() for code in request.fir_codes}

    try:
        # Build SQLAlchemy query
        query = db.query(Invoice)

        # If fir_codes provided: JOIN fir_entries and filter by fir_code IN
        if requested_fir_codes:
            query = (
                query.join(FIREntry, Invoice.invoice_id == FIREntry.invoice_id)
                .filter(func.upper(FIREntry.fir_code).in_(requested_fir_codes))
            )
            # Apply DISTINCT on invoice_id to avoid duplicates from the JOIN
            query = query.with_entities(Invoice).distinct(Invoice.invoice_id)

        # Apply date range filter (BETWEEN inclusive)
        if date_from and date_to:
            query = query.filter(
                Invoice.invoice_date.between(date_from, date_to)
            )
        elif date_from:
            query = query.filter(Invoice.invoice_date >= date_from)
        elif date_to:
            query = query.filter(Invoice.invoice_date <= date_to)

        # Apply vendor filter: case-insensitive substring match
        if request.vendor:
            query = query.filter(
                func.upper(Invoice.vendor).like(
                    f"%{request.vendor.upper()}%"
                )
            )

        # Apply currency filter: case-insensitive exact match
        if request.currency:
            query = query.filter(
                func.upper(Invoice.currency) == request.currency.upper()
            )

        # Apply min_amount filter: total_amount >= min_amount
        if request.min_amount is not None:
            query = query.filter(Invoice.total_amount >= request.min_amount)

        # Silently ignore: aircraft_type, registration, origin, destination,
        # tenant_id (columns don't exist yet — Req 1.7-1.10, 10.1, 10.3)

        # Execute query
        invoices = query.all()

        # For each invoice, compute fir_match_score and build response
        results_with_score: list[tuple[Invoice, str]] = []
        for invoice in invoices:
            invoice_fir_codes = {
                entry.fir_code.upper()
                for entry in invoice.fir_entries
                if entry.fir_code
            }
            score = compute_fir_match_score(invoice_fir_codes, requested_fir_codes)
            results_with_score.append((invoice, score))

        # Sort by score descending (strong > moderate > none),
        # then invoice_date descending
        results_with_score.sort(
            key=lambda x: (
                _SCORE_ORDER.get(x[1], 3),
                -(x[0].invoice_date.toordinal() if x[0].invoice_date else 0),
            )
        )

        # Limit to MAX_RESULTS
        results_with_score = results_with_score[:MAX_RESULTS]

        # Build response
        response_results = []
        for invoice, score in results_with_score:
            fir_entry_responses = [
                FIREntryResponse(
                    fir_entry_id=str(entry.fir_entry_id),
                    fir_code=entry.fir_code or "",
                    fir_name=entry.fir_name,
                    country=entry.country,
                    amount=float(entry.amount) if entry.amount is not None else None,
                    currency=entry.currency,
                    confidence=float(entry.confidence) if entry.confidence is not None else None,
                    extraction_method=entry.extraction_method,
                )
                for entry in invoice.fir_entries
            ]

            response_results.append(
                InvoiceRecordResponse(
                    invoice_id=str(invoice.invoice_id),
                    filename=invoice.filename or "",
                    vendor=invoice.vendor or "",
                    invoice_number=invoice.invoice_number,
                    invoice_date=invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                    total_amount=float(invoice.total_amount) if invoice.total_amount is not None else None,
                    currency=invoice.currency,
                    language=invoice.language,
                    pages=invoice.pages,
                    processing_date=invoice.processing_date.isoformat() if invoice.processing_date else None,
                    fir_entries=fir_entry_responses,
                    fir_match_score=score,
                )
            )

        return InvoiceSearchResponse(
            results=response_results,
            total_count=len(response_results),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Database error during invoice search: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error during invoice search"},
        )
