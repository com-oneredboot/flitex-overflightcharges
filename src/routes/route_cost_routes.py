"""Route Cost calculation API endpoint.

This module provides REST API endpoints for calculating overflight charges
using the enhanced pipeline:
  Enhanced Route Parser → FIR Intersection Engine → Dual Validator →
  Charge Calculator → Session Builder → LLM Auditor (async)

- POST /api/route-costs - Calculate route cost with full session assembly
- GET  /api/route-costs/{calculation_id}/session - Retrieve session details

Validates Requirements: 10.1, 12.1, 13.3, 17.1, 17.2
"""

import logging
import time
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import ParsingException, ValidationException
from src.models.overflight_calculation_session import OverflightCalculationSession
from src.schemas.route_cost import (
    CoverageGap,
    CoverageSummary,
    FIRChargeBreakdown,
    RouteCostRequest,
    RouteCostResponse,
)
from src.services.charge_calculation import DefaultOverflightChargeCalculator
from src.services.dual_validator import DualValidator
from src.services.fir_intersection_engine import FIRIntersectionEngine
from src.services.llm_auditor import LLMAuditor
from src.services.route_parser import RouteParser
from src.services.session_builder import SessionBuilder

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/route-costs", tags=["Route Cost Calculation"])


def _parse_flight_date(raw: str | None) -> date | None:
    """Parse a YYYY-MM-DD string into a date, returning None on failure."""
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        logger.warning("Invalid flight_date format: %s — expected YYYY-MM-DD", raw)
        return None


def _build_fir_breakdown(
    charges: list[dict],
    fir_crossings_list: list[dict],
) -> list[FIRChargeBreakdown]:
    """Merge charge dicts with FIR crossing distance data into response models.

    For each charge, look up the matching FIR crossing by icao_code to attach
    distance and entry/exit point data. If a crossing produced a charge error
    (no formula, execution failure), the distance fields come from the crossing
    record directly.
    """
    # Build a lookup of crossing data keyed by (icao_code, sequence) for
    # multi-crossing same-FIR scenarios. Fall back to icao_code-only lookup.
    crossing_by_code: dict[str, dict] = {}
    for cx in fir_crossings_list:
        code = cx.get("icao_code", "")
        if code not in crossing_by_code:
            crossing_by_code[code] = cx

    breakdown: list[FIRChargeBreakdown] = []
    for charge in charges:
        icao = charge.get("icao_code", "")
        cx = crossing_by_code.get(icao, {})

        entry_pt = cx.get("entry_point")
        exit_pt = cx.get("exit_point")

        breakdown.append(
            FIRChargeBreakdown(
                icao_code=icao,
                fir_name=charge.get("fir_name", ""),
                country_code=charge.get("country_code", ""),
                charge_amount=charge.get("charge_amount", 0.0),
                currency=charge.get("currency", "USD"),
                formula_code=charge.get("formula_code", "NONE"),
                formula_version=charge.get("formula_version"),
                effective_date=charge.get("formula_effective_date"),
                segment_distance_km=cx.get("segment_distance_km"),
                segment_distance_nm=cx.get("segment_distance_nm"),
                gc_entry_exit_distance_km=cx.get("gc_entry_exit_distance_km"),
                gc_entry_exit_distance_nm=cx.get("gc_entry_exit_distance_nm"),
                entry_point=(
                    {"lat": entry_pt[0], "lon": entry_pt[1]}
                    if isinstance(entry_pt, (list, tuple)) and len(entry_pt) == 2
                    else entry_pt
                ),
                exit_point=(
                    {"lat": exit_pt[0], "lon": exit_pt[1]}
                    if isinstance(exit_pt, (list, tuple)) and len(exit_pt) == 2
                    else exit_pt
                ),
                distance_method=charge.get("distance_method", "segment"),
                charge_type=charge.get("charge_type", "overflight"),
            )
        )

    return breakdown


def _build_coverage_gaps(
    chain_continuity_failures: list[dict],
    crossings: list,
    total_fir_distance_nm: float,
) -> tuple[list[CoverageGap], CoverageSummary]:
    """Map chain continuity failures to CoverageGap objects and compute summary.

    For each failure, maps pair indices to ICAO codes from the crossings list,
    converts gap_distance_m to nautical miles, and converts coordinate tuples
    to {lat, lon} dicts. Skips failures with out-of-bounds pair indices.

    Args:
        chain_continuity_failures: List of failure dicts from
            FIRIntersectionEngine._validate_chain_continuity().
        crossings: Ordered list of FIR crossing records with .icao_code attribute.
        total_fir_distance_nm: Sum of FIR segment distances in nautical miles.

    Returns:
        Tuple of (list of CoverageGap objects, CoverageSummary).

    Validates Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 1.5
    """
    gaps: list[CoverageGap] = []
    num_crossings = len(crossings)

    for failure in chain_continuity_failures:
        pair = failure.get("pair", ())
        if len(pair) != 2:
            logger.warning("Skipping chain continuity failure with invalid pair: %s", pair)
            continue

        i, j = pair
        if i < 0 or i >= num_crossings or j < 0 or j >= num_crossings:
            logger.warning(
                "Skipping chain continuity failure with out-of-bounds pair indices (%d, %d) "
                "for crossings list of length %d",
                i, j, num_crossings,
            )
            continue

        exit_pt = failure.get("exit_point", ())
        entry_pt = failure.get("entry_point", ())

        gaps.append(
            CoverageGap(
                after_fir_icao=crossings[i].icao_code,
                before_fir_icao=crossings[j].icao_code,
                exit_point={"lat": exit_pt[0], "lon": exit_pt[1]},
                entry_point={"lat": entry_pt[0], "lon": entry_pt[1]},
                gap_distance_nm=failure.get("gap_distance_m", 0.0) / 1852.0,
            )
        )

    total_gap_distance_nm = sum(gap.gap_distance_nm for gap in gaps)
    total_route_distance_nm = total_fir_distance_nm + total_gap_distance_nm

    if total_route_distance_nm == 0:
        coverage_pct = 100.0
    else:
        coverage_pct = round((total_fir_distance_nm / total_route_distance_nm) * 100, 1)

    summary = CoverageSummary(
        total_gap_distance_nm=total_gap_distance_nm,
        gap_count=len(gaps),
        coverage_pct=coverage_pct,
    )

    return gaps, summary


@router.post("", response_model=RouteCostResponse, status_code=status.HTTP_200_OK)
async def calculate_route_cost(
    request: RouteCostRequest,
    db: Session = Depends(get_db),
) -> RouteCostResponse:
    """Calculate overflight charges for a flight route using the enhanced pipeline.

    Pipeline stages:
        1. Enhanced Route Parser  → TokenResolutionResult
        2. FIR Intersection Engine → FIRIntersectionResult
        3. Dual Validator          → DualValidationResult
        4. Charge Calculator       → list[dict] (one per FIR crossing)
        5. Session Builder         → build_data_provenance, build_session, store_session
        6. LLM Auditor             → audit_async (fire-and-forget, non-blocking)
        7. Return API response with calculation_id and FIR crossings with distances

    Accepts existing request parameters plus flight_number, flight_date, callsign.
    Returns response including calculationId and per-FIR distance data.

    Validates Requirements: 10.1, 12.1, 13.3

    Args:
        request: Route cost calculation request with all required fields.
        db: Database session (injected).

    Returns:
        Route cost response with calculation_id, total_cost, per-FIR breakdown
        including distance data.

    Raises:
        ParsingException: If route_string is invalid (400).
        ValidationException: If validation fails (422).
    """
    start_time = time.time()

    try:
        flight_date = _parse_flight_date(request.flight_date)

        # ------------------------------------------------------------------
        # 1. Enhanced Route Parser → TokenResolutionResult
        # ------------------------------------------------------------------
        route_parser = RouteParser()
        token_result = route_parser.parse_route(
            route_string=request.route_string,
            origin=request.origin,
            destination=request.destination,
            flight_date=flight_date or date.today(),
            db=db,
        )

        logger.info(
            "Route parsing complete: %d resolved, %d unresolved",
            len(token_result.resolved_waypoints),
            len(token_result.unresolved_tokens),
        )

        # ------------------------------------------------------------------
        # 2. FIR Intersection Engine → FIRIntersectionResult
        # ------------------------------------------------------------------
        fir_engine = FIRIntersectionEngine()
        fir_result = fir_engine.compute_fir_crossings(
            coordinates=token_result.route_linestring_coords,
            db=db,
        )

        logger.info(
            "FIR intersection complete: %d crossings, %.2f nm total",
            len(fir_result.crossings),
            fir_result.total_distance_nm,
        )

        # ------------------------------------------------------------------
        # 3. Dual Validator → DualValidationResult
        # ------------------------------------------------------------------
        dual_validator = DualValidator()
        validation_result = dual_validator.validate(
            coordinates=token_result.route_linestring_coords,
            postgis_crossings=fir_result.crossings,
            db=db,
        )

        if validation_result.flagged_for_review:
            logger.warning(
                "Route flagged for review: fir_match=%s, max_divergence=%.2f%%",
                validation_result.fir_lists_match,
                validation_result.max_distance_divergence_pct,
            )

        # ------------------------------------------------------------------
        # 4. Charge Calculator → list of charge dicts (one per FIR crossing)
        # ------------------------------------------------------------------
        charge_calculator = DefaultOverflightChargeCalculator()
        charges: list[dict] = []
        for crossing in fir_result.crossings:
            try:
                charge = charge_calculator.calculate_fir_charge(
                    fir_crossing=crossing,
                    aircraft_type=request.aircraft_type,
                    mtow_kg=request.mtow_kg,
                    db=db,
                )
                charges.append(charge)
            except Exception as exc:
                logger.error(
                    "Charge calculation failed for FIR %s: %s",
                    crossing.icao_code,
                    str(exc),
                    exc_info=True,
                )
                # Include a zero-charge entry so the FIR still appears in results
                charges.append({
                    "icao_code": crossing.icao_code,
                    "fir_name": crossing.fir_name,
                    "country": crossing.country,
                    "country_code": crossing.country_code,
                    "formula_code": "NONE",
                    "formula_version": 0,
                    "formula_effective_date": None,
                    "unit_rate": 0.0,
                    "unit_rate_source": "N/A",
                    "unit_rate_effective_date": None,
                    "distance_factor": 0.0,
                    "weight_factor": 0.0,
                    "charge_amount": 0.0,
                    "currency": "USD",
                    "charge_in_usd": 0.0,
                    "exchange_rate": 1.0,
                    "exchange_rate_date": None,
                    "distance_used_km": round(crossing.segment_distance_km, 4),
                    "distance_method": "segment",
                    "bilateral_exemption": None,
                    "charge_type": "overflight",
                    "justification": f"Charge calculation failed for FIR {crossing.icao_code}: {exc}",
                })

        # ------------------------------------------------------------------
        # 5. Session Builder → build_data_provenance, build_session, store_session
        # ------------------------------------------------------------------
        calculation_id = None
        calc_session = None
        try:
            session_builder = SessionBuilder()

            input_data = {
                "route_string": request.route_string,
                "origin": request.origin,
                "destination": request.destination,
                "aircraft_type": request.aircraft_type,
                "mtow_kg": request.mtow_kg,
                "flight_number": request.flight_number,
                "flight_date": request.flight_date,
                "callsign": request.callsign,
            }

            data_provenance = session_builder.build_data_provenance(
                token_result=token_result,
                charges=charges,
                db=db,
            )

            calc_session = session_builder.build_session(
                input_data=input_data,
                token_result=token_result,
                fir_crossings=fir_result,
                charges=charges,
                validation=validation_result,
                data_provenance=data_provenance,
                db=db,
            )

            calculation_id = session_builder.store_session(
                session=calc_session,
                db=db,
            )

            db.commit()
        except Exception as session_exc:
            db.rollback()
            logger.warning(
                "Session storage failed (non-blocking): %s",
                str(session_exc),
            )
            # Generate a calculation_id even if storage failed
            import uuid as _uuid
            calculation_id = str(_uuid.uuid4())

        # ------------------------------------------------------------------
        # 6. LLM Auditor → audit_async (fire-and-forget, non-blocking)
        # ------------------------------------------------------------------
        try:
            if calc_session:
                llm_auditor = LLMAuditor()
                llm_auditor.audit_async(session=calc_session, db=db)
        except Exception as llm_exc:
            # LLM audit must never block or fail the response
            logger.warning(
                "LLM audit initiation failed (non-blocking): %s",
                str(llm_exc),
            )

        # ------------------------------------------------------------------
        # 7. Build and return API response
        # ------------------------------------------------------------------
        # Build coverage gaps from chain continuity failures
        if fir_result.chain_continuity_failures:
            coverage_gaps, coverage_summary = _build_coverage_gaps(
                chain_continuity_failures=fir_result.chain_continuity_failures,
                crossings=fir_result.crossings,
                total_fir_distance_nm=fir_result.total_distance_nm,
            )
        else:
            coverage_gaps = []
            coverage_summary = CoverageSummary(
                total_gap_distance_nm=0.0,
                gap_count=0,
                coverage_pct=100.0,
            )

        # Build FIR crossing dicts for the breakdown helper
        fir_crossings_list = [
            {
                "icao_code": c.icao_code,
                "segment_distance_km": c.segment_distance_km,
                "segment_distance_nm": c.segment_distance_nm,
                "gc_entry_exit_distance_km": c.gc_entry_exit_distance_km,
                "gc_entry_exit_distance_nm": c.gc_entry_exit_distance_nm,
                "entry_point": c.entry_point,
                "exit_point": c.exit_point,
            }
            for c in fir_result.crossings
        ]

        fir_breakdown = _build_fir_breakdown(charges, fir_crossings_list)

        total_cost = sum(c.get("charge_in_usd", 0.0) for c in charges)

        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "Route cost calculation completed",
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 200,
                "duration_ms": duration_ms,
                "route_string": request.route_string,
                "total_cost": total_cost,
                "calculation_duration_ms": duration_ms,
                "calculation_id": calculation_id,
                "fir_count": len(fir_breakdown),
            },
        )

        return RouteCostResponse(
            calculation_id=calculation_id,
            total_cost=round(total_cost, 2),
            currency="USD",
            fir_breakdown=fir_breakdown,
            total_distance_km=round(fir_result.total_distance_km, 4),
            total_distance_nm=round(fir_result.total_distance_nm, 4),
            fir_count=len(fir_result.crossings),
            coverage_gaps=coverage_gaps,
            coverage_summary=coverage_summary,
        )

    except ParsingException as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "Invalid route string: %s",
            e.message,
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 400,
                "duration_ms": duration_ms,
                "route_string": request.route_string,
                "error": e.message,
            },
        )
        raise

    except ValidationException as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.warning(
            "Validation error: %s",
            e.message,
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 422,
                "duration_ms": duration_ms,
                "error": e.message,
            },
        )
        raise

    except Exception as e:
        db.rollback()
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Unexpected error in route cost calculation: %s",
            str(e),
            extra={
                "method": "POST",
                "path": "/api/route-costs",
                "status_code": 500,
                "duration_ms": duration_ms,
                "route_string": request.route_string,
                "error": str(e),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "detail": "An unexpected error occurred during route cost calculation",
                "status_code": 500,
            },
        )


@router.get(
    "/{calculation_id}/session",
    status_code=status.HTTP_200_OK,
)
async def get_session_details(
    calculation_id: UUID,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Retrieve the full calculation session details by calculation_id.

    Returns the complete session_data JSONB object stored during calculation,
    including route resolution tokens, validation results, data provenance,
    and all other session sections.

    Validates Requirements: 17.1, 17.2

    Args:
        calculation_id: UUID of the calculation session.
        db: Database session (injected).

    Returns:
        Complete session_data JSON object.

    Raises:
        HTTPException 404: If no session found for the given calculation_id.
    """
    session_record = (
        db.query(OverflightCalculationSession)
        .filter(OverflightCalculationSession.calculation_id == calculation_id)
        .first()
    )

    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No calculation session found for calculation_id: {calculation_id}",
        )

    return JSONResponse(content=session_record.session_data)
