"""Session Builder for assembling and storing Calculation Session JSON objects.

This module provides the SessionBuilder class that assembles complete, auditable
Calculation Session JSON objects from the outputs of the enhanced route parser,
FIR intersection engine, dual validator, and charge calculator. Each session
captures all inputs, resolution steps, FIR crossings, charges, validation results,
and data provenance for invoice dispute evidence.

The primary identifier is `calculation_id` (UUID), used consistently across
Python/DB (snake_case) and JSON/Angular (camelCase).

Validates Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8,
                        10.9, 10.10, 10.11, 11.1, 11.2, 11.3, 11.4
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.fir_charge import FirCharge
from src.models.iata_fir import IataFir
from src.models.overflight_calculation_session import OverflightCalculationSession
from src.models.route_calculation import RouteCalculation
from src.services.dual_validator import DualValidationResult
from src.services.fir_intersection_engine import (
    FIRCrossingRecord,
    FIRIntersectionResult,
)
from src.services.route_parser import TokenRecord, TokenResolutionResult

logger = logging.getLogger(__name__)

CALCULATOR_VERSION = "2.0.0"


class SessionBuilder:
    """Assembles complete Calculation Session JSON objects and persists them.

    The session builder takes outputs from each pipeline stage and assembles
    them into a self-contained, auditable JSON record following the schema
    defined in the design document. Sessions are stored as JSONB in the
    calculations.overflight_calculation_sessions table.

    Validates Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7,
                            10.8, 10.9, 10.10, 10.11
    """

    def build_session(
        self,
        input_data: dict,
        token_result: TokenResolutionResult,
        fir_crossings: FIRIntersectionResult,
        charges: list[dict],
        validation: DualValidationResult,
        data_provenance: dict,
        db: Session,
    ) -> dict:
        """Assemble complete Calculation Session JSON object.

        Generates a new UUID for calculation_id and builds each section of the
        session JSON from the input parameters. Converts dataclass objects to
        dicts for JSON serialization. Includes LLM sanity check placeholder
        (verdict "pending") and chain continuity from fir_crossings result.

        Args:
            input_data: Dict with route_string, origin, destination,
                aircraft_type, mtow_kg, flight_number, flight_date, callsign,
                and optionally user_id.
            token_result: Complete token resolution result from enhanced parser.
            fir_crossings: FIR intersection result with crossings and distances.
            charges: List of charge dicts from the charge calculator.
            validation: Dual-system validation result (PostGIS vs Shapely).
            data_provenance: Dict with version/source info for FIR boundaries,
                unit rates, nav data, exchange rates, and formulas.
            db: SQLAlchemy database session.

        Returns:
            Complete Calculation Session dict ready for JSONB storage.

        Validates Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7,
                                10.8, 10.9, 10.10, 10.11
        """
        calculation_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        session = {
            "session": self._build_session_metadata(
                calculation_id=calculation_id,
                timestamp=timestamp,
                user_id=input_data.get("user_id"),
            ),
            "input": self._build_input_section(input_data),
            "route_resolution": self._build_route_resolution_section(
                token_result, fir_crossings
            ),
            "fir_crossings": self._build_fir_crossings_section(fir_crossings),
            "fir_charges": charges,
            "totals": self._build_totals(charges),
            "validation": self._build_validation_section(
                validation, fir_crossings
            ),
            "data_provenance": data_provenance,
            "comparison": self._build_comparison_section(input_data),
        }

        logger.info(
            "Assembled calculation session",
            extra={
                "calculation_id": calculation_id,
                "origin": input_data.get("origin"),
                "destination": input_data.get("destination"),
                "fir_count": len(fir_crossings.crossings),
            },
        )

        return session

    def store_session(self, session: dict, db: Session) -> str:
        """Store session as JSONB, update summary tables. Returns calculation_id.

        Persists the complete Calculation Session to the
        ``calculations.overflight_calculation_sessions`` table, then creates
        derived summary records in ``route_calculations`` and ``fir_charges``
        so that existing queries and reports continue to work.

        All database operations happen within the caller's transaction — the
        caller is responsible for committing or rolling back.

        Args:
            session: Complete Calculation Session dict (output of build_session).
            db: SQLAlchemy database session.

        Returns:
            The calculation_id (UUID string) of the stored session.

        Validates Requirements: 11.1, 11.2, 11.3, 11.4
        """
        session_meta = session["session"]
        input_data = session["input"]
        calculation_id = session_meta["calculation_id"]

        # --- 1. INSERT into calculations.overflight_calculation_sessions ---
        # Coerce flight_date to a date object if it's a string
        flight_date_raw = input_data.get("flight_date")
        flight_date_val = self._coerce_date(flight_date_raw)

        # Coerce user_id to a UUID if present
        user_id_raw = session_meta.get("user_id")
        user_id_val = uuid.UUID(user_id_raw) if user_id_raw else None

        calc_session = OverflightCalculationSession(
            calculation_id=uuid.UUID(calculation_id),
            session_type="planned",
            session_data=session,
            origin=input_data.get("origin", ""),
            destination=input_data.get("destination", ""),
            flight_number=input_data.get("flight_number"),
            flight_date=flight_date_val,
            aircraft_type=input_data.get("aircraft_type", ""),
            mtow_kg=Decimal(str(input_data.get("mtow_kg", 0))),
            calculator_version=session_meta.get(
                "calculator_version", CALCULATOR_VERSION
            ),
            user_id=user_id_val,
        )
        db.add(calc_session)
        db.flush()  # Ensure calculation_id is available for FK references

        # --- 2. INSERT into route_calculations (derived summary) ---
        route_resolution = session.get("route_resolution", {})
        totals = session.get("totals", {})

        route_calc = RouteCalculation(
            route_string=input_data.get("route_string", ""),
            origin=input_data.get("origin", ""),
            destination=input_data.get("destination", ""),
            aircraft_type=input_data.get("aircraft_type", ""),
            mtow_kg=Decimal(str(input_data.get("mtow_kg", 0))),
            total_cost=Decimal(str(totals.get("total_usd", 0))),
            currency="USD",
            session_id=uuid.UUID(calculation_id),
            flight_number=input_data.get("flight_number"),
            flight_date=flight_date_val,
            total_distance_km=Decimal(
                str(route_resolution.get("total_distance_km", 0))
            ),
            total_distance_nm=Decimal(
                str(route_resolution.get("total_distance_nm", 0))
            ),
            fir_count=totals.get("fir_count", 0),
        )
        db.add(route_calc)
        db.flush()  # Get route_calc.id for fir_charges FK

        # --- 3. INSERT fir_charges (derived summary per FIR) ---
        # Pre-load active FIR IDs keyed by icao_code for efficient lookup
        fir_id_map = self._build_fir_id_map(session.get("fir_charges", []), db)

        for charge in session.get("fir_charges", []):
            icao_code = charge.get("icao_code", "")
            fir_id = fir_id_map.get(icao_code)
            if fir_id is None:
                logger.warning(
                    "No active FIR found for icao_code=%s, skipping fir_charge",
                    icao_code,
                )
                continue

            fir_charge = FirCharge(
                calculation_id=route_calc.id,
                fir_id=fir_id,
                icao_code=icao_code,
                fir_name=charge.get("fir_name", ""),
                country_code=charge.get("country_code", ""),
                charge_amount=Decimal(str(charge.get("charge_amount", 0))),
                currency=charge.get("currency", "USD"),
                segment_distance_km=Decimal(
                    str(charge.get("distance_used_km", 0))
                ),
                segment_distance_nm=self._lookup_segment_nm(
                    icao_code, session.get("fir_crossings", [])
                ),
                gc_entry_exit_distance_km=self._lookup_gc_km(
                    icao_code, session.get("fir_crossings", [])
                ),
                gc_entry_exit_distance_nm=self._lookup_gc_nm(
                    icao_code, session.get("fir_crossings", [])
                ),
                distance_method=charge.get("distance_method", "segment"),
                charge_type=charge.get("charge_type", "overflight"),
                bilateral_exemption=charge.get("bilateral_exemption"),
                session_id=uuid.UUID(calculation_id),
            )
            db.add(fir_charge)

        db.flush()

        logger.info(
            "Stored calculation session and summary records",
            extra={
                "calculation_id": calculation_id,
                "route_calculation_id": str(route_calc.id),
                "fir_charges_count": len(session.get("fir_charges", [])),
            },
        )

        return calculation_id

    # ------------------------------------------------------------------
    # Private helpers for store_session
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_date(value) -> date | None:
        """Convert a string or date to a date object, or return None."""
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except (ValueError, TypeError):
                return None
        return None

    @staticmethod
    def _build_fir_id_map(charges: list[dict], db: Session) -> dict[str, uuid.UUID]:
        """Build a mapping of icao_code → active IataFir.id for all FIRs in charges."""
        icao_codes = list({c.get("icao_code", "") for c in charges if c.get("icao_code")})
        if not icao_codes:
            return {}

        firs = (
            db.query(IataFir.icao_code, IataFir.id)
            .filter(IataFir.icao_code.in_(icao_codes), IataFir.is_active.is_(True))
            .all()
        )
        return {row.icao_code: row.id for row in firs}

    @staticmethod
    def _lookup_segment_nm(icao_code: str, fir_crossings: list[dict]) -> Decimal | None:
        """Find segment_distance_nm for a given icao_code from fir_crossings."""
        for crossing in fir_crossings:
            if crossing.get("icao_code") == icao_code:
                val = crossing.get("segment_distance_nm")
                return Decimal(str(val)) if val is not None else None
        return None

    @staticmethod
    def _lookup_gc_km(icao_code: str, fir_crossings: list[dict]) -> Decimal | None:
        """Find gc_entry_exit_distance_km for a given icao_code from fir_crossings."""
        for crossing in fir_crossings:
            if crossing.get("icao_code") == icao_code:
                val = crossing.get("gc_entry_exit_distance_km")
                return Decimal(str(val)) if val is not None else None
        return None

    @staticmethod
    def _lookup_gc_nm(icao_code: str, fir_crossings: list[dict]) -> Decimal | None:
        """Find gc_entry_exit_distance_nm for a given icao_code from fir_crossings."""
        for crossing in fir_crossings:
            if crossing.get("icao_code") == icao_code:
                val = crossing.get("gc_entry_exit_distance_nm")
                return Decimal(str(val)) if val is not None else None
        return None

    def build_data_provenance(
        self,
        token_result: TokenResolutionResult,
        charges: list[dict],
        db: Session,
    ) -> dict:
        """Build the data_provenance section by querying actual version info from the database.

        Queries the database for version/source metadata about each data source
        used in the calculation: FIR boundaries, unit rates, navigation data,
        exchange rates, and formulas.

        Args:
            token_result: Token resolution result, used to determine which
                nav data tables were used during waypoint resolution.
            charges: List of charge dicts, used to extract exchange rate
                and formula metadata already computed during charge calculation.
            db: SQLAlchemy database session.

        Returns:
            Dict matching the data_provenance schema from the design document.

        Validates Requirements: 10.9
        """
        return {
            "fir_boundaries": self._provenance_fir_boundaries(db),
            "unit_rates": self._provenance_unit_rates(db),
            "nav_data": self._provenance_nav_data(token_result),
            "exchange_rates": self._provenance_exchange_rates(charges),
            "formulas": self._provenance_formulas(charges),
        }

    def _provenance_fir_boundaries(self, db: Session) -> dict:
        """Query FIR boundary version info from reference.fir_boundaries.

        Uses MAX(created_at) as the effective date proxy since the table
        does not have an explicit version_id column. The source is always
        the reference.fir_boundaries table.

        Validates Requirements: 10.9
        """
        result: dict = {
            "version_id": None,
            "effective_date": None,
            "source": "reference.fir_boundaries",
            "airac_cycle": None,
        }
        try:
            row = db.execute(
                text(
                    "SELECT COUNT(*) AS cnt, MAX(created_at) AS latest "
                    "FROM reference.fir_boundaries"
                )
            ).fetchone()
            if row and row.latest:
                result["effective_date"] = row.latest.isoformat() if hasattr(row.latest, "isoformat") else str(row.latest)
                result["version_id"] = f"fir-{row.cnt}-{result['effective_date'][:10]}"
        except Exception:
            logger.debug("Could not query FIR boundary provenance", exc_info=True)
        return result

    def _provenance_unit_rates(self, db: Session) -> dict:
        """Query unit rate version info from eurocontrol_unit_rates.

        Fetches the most recent rate period to determine last_updated and
        scrape_date. The source is always EUROCONTROL.

        Validates Requirements: 10.9
        """
        result: dict = {
            "last_updated": None,
            "source": "EUROCONTROL",
            "scrape_date": None,
        }
        try:
            nested = db.begin_nested()
            try:
                row = db.execute(
                    text(
                        "SELECT MAX(date_to) AS latest_period, "
                        "       MAX(date_from) AS latest_from "
                        "FROM eurocontrol_unit_rates"
                    )
                ).fetchone()
                nested.commit()
                if row:
                    if row.latest_period:
                        result["last_updated"] = (
                            row.latest_period.isoformat()
                            if hasattr(row.latest_period, "isoformat")
                            else str(row.latest_period)
                        )
                    if row.latest_from:
                        result["scrape_date"] = (
                            row.latest_from.isoformat()
                            if hasattr(row.latest_from, "isoformat")
                            else str(row.latest_from)
                        )
            except Exception:
                nested.rollback()
                raise
        except Exception:
            logger.debug("Could not query unit rate provenance", exc_info=True)
        return result

    def _provenance_nav_data(self, token_result: TokenResolutionResult) -> dict:
        """Derive navigation data provenance from the token resolution result.

        Extracts the distinct source_table values from resolved waypoints to
        populate tables_used. AIRAC cycle is not stored in the database, so
        it is left as None (to be populated by the freshness checker when
        available).

        Validates Requirements: 10.9
        """
        tables_used: list[str] = sorted(
            {
                wp.source_table
                for wp in token_result.resolved_waypoints
                if wp.source_table
            }
        )
        return {
            "airac_cycle": None,
            "tables_used": tables_used,
        }

    @staticmethod
    def _provenance_exchange_rates(charges: list[dict]) -> dict:
        """Extract exchange rate provenance from the computed charges.

        Uses the most recent exchange_rate_date found across all charge
        entries. The source is EUROCONTROL (rates come from the
        eurocontrol_unit_rates table's ex_rate_to_eur column).

        Validates Requirements: 10.9
        """
        latest_date: str | None = None
        for charge in charges:
            erd = charge.get("exchange_rate_date")
            if erd and (latest_date is None or str(erd) > str(latest_date)):
                latest_date = str(erd)
        return {
            "date": latest_date,
            "source": "EUROCONTROL",
        }

    @staticmethod
    def _provenance_formulas(charges: list[dict]) -> dict:
        """Extract formula registry provenance from the computed charges.

        Collects distinct formula codes used and determines the registry
        version from the maximum formula_version across all charges.

        Validates Requirements: 10.9
        """
        formulas_used: list[str] = sorted(
            {
                charge.get("formula_code", "")
                for charge in charges
                if charge.get("formula_code")
            }
        )
        max_version = 0
        for charge in charges:
            v = charge.get("formula_version", 0)
            if isinstance(v, (int, float)) and v > max_version:
                max_version = v
        return {
            "registry_version": str(max_version) if max_version else "0",
            "formulas_used": formulas_used,
        }

    def _build_session_metadata(
        self,
        calculation_id: str,
        timestamp: str,
        user_id: str | None,
    ) -> dict:
        """Build the session metadata section.

        Args:
            calculation_id: UUID string for this calculation.
            timestamp: ISO 8601 timestamp string.
            user_id: UUID string of the user, or None.

        Returns:
            Dict with calculation_id, timestamp, calculator_version, user_id.

        Validates Requirements: 10.11
        """
        return {
            "calculation_id": calculation_id,
            "timestamp": timestamp,
            "calculator_version": CALCULATOR_VERSION,
            "user_id": user_id,
        }

    def _build_input_section(self, input_data: dict) -> dict:
        """Build the input section from request data.

        Args:
            input_data: Dict with route parameters from the API request.

        Returns:
            Dict with route_string, origin, destination, aircraft_type,
            mtow_kg, flight_number, flight_date, callsign.

        Validates Requirements: 10.2
        """
        return {
            "route_string": input_data.get("route_string", ""),
            "origin": input_data.get("origin", ""),
            "destination": input_data.get("destination", ""),
            "aircraft_type": input_data.get("aircraft_type", ""),
            "mtow_kg": input_data.get("mtow_kg", 0),
            "flight_number": input_data.get("flight_number"),
            "flight_date": input_data.get("flight_date"),
            "callsign": input_data.get("callsign"),
        }

    def _build_route_resolution_section(
        self,
        token_result: TokenResolutionResult,
        fir_crossings: FIRIntersectionResult,
    ) -> dict:
        """Build the route_resolution section from token resolution results.

        Converts TokenRecord and Waypoint dataclasses to dicts for JSON
        serialization. Includes the route linestring as GeoJSON and total
        distances from the FIR intersection result.

        Args:
            token_result: Complete token resolution result from enhanced parser.
            fir_crossings: FIR intersection result for total distance values.

        Returns:
            Dict with tokens, resolved_waypoints, unresolved, route_linestring,
            total_distance_km, total_distance_nm.

        Validates Requirements: 10.3, 10.4, 10.5
        """
        tokens = [self._token_record_to_dict(t) for t in token_result.tokens]

        resolved_waypoints = [
            {
                "ident": wp.identifier,
                "lat": wp.latitude,
                "lon": wp.longitude,
                "source_table": wp.source_table,
                "alternatives_count": 0,
            }
            for wp in token_result.resolved_waypoints
        ]

        unresolved = [
            {
                "token": t.raw,
                "classification": t.classification,
                "reason": t.reason_code,
                "reason_code": t.reason_code,
            }
            for t in token_result.unresolved_tokens
        ]

        # Build GeoJSON LineString from route coordinates
        route_linestring = {
            "type": "LineString",
            "coordinates": list(token_result.route_linestring_coords),
        }

        return {
            "tokens": tokens,
            "resolved_waypoints": resolved_waypoints,
            "unresolved": unresolved,
            "route_linestring": route_linestring,
            "total_distance_km": fir_crossings.total_distance_km,
            "total_distance_nm": fir_crossings.total_distance_nm,
        }

    def _token_record_to_dict(self, token: TokenRecord) -> dict:
        """Convert a TokenRecord dataclass to a JSON-serializable dict.

        Args:
            token: TokenRecord instance from the enhanced parser.

        Returns:
            Dict matching the session JSON token schema.

        Validates Requirements: 10.3
        """
        return {
            "raw": token.raw,
            "classification": token.classification,
            "action": token.action,
            "reason_code": token.reason_code,
            "source_table": token.source_table,
            "resolved_lat": token.resolved_lat,
            "resolved_lon": token.resolved_lon,
            "alternatives_count": token.alternatives_count,
            "disambiguation_distance_nm": token.disambiguation_distance_nm,
            "expanded_to": token.expanded_waypoints,
            "original_token": token.original_token,
            "trimmed_to": token.trimmed_to,
            "discard_details": token.discard_details,
        }

    def _build_fir_crossings_section(
        self, fir_crossings: FIRIntersectionResult
    ) -> list[dict]:
        """Build the fir_crossings array from FIR intersection results.

        Converts FIRCrossingRecord dataclasses to dicts matching the session
        JSON schema, with entry/exit points as nested lat/lon objects.

        Args:
            fir_crossings: FIR intersection result with crossing records.

        Returns:
            List of dicts, one per FIR crossing.

        Validates Requirements: 10.6
        """
        return [
            {
                "sequence": crossing.sequence,
                "icao_code": crossing.icao_code,
                "fir_name": crossing.fir_name,
                "country": crossing.country,
                "country_code": crossing.country_code,
                "entry_point": {
                    "lat": crossing.entry_point[0],
                    "lon": crossing.entry_point[1],
                },
                "exit_point": {
                    "lat": crossing.exit_point[0],
                    "lon": crossing.exit_point[1],
                },
                "segment_distance_km": crossing.segment_distance_km,
                "segment_distance_nm": crossing.segment_distance_nm,
                "gc_entry_exit_distance_km": crossing.gc_entry_exit_distance_km,
                "gc_entry_exit_distance_nm": crossing.gc_entry_exit_distance_nm,
                "segment_geometry": crossing.segment_geometry,
                "calculation_method": crossing.calculation_method,
            }
            for crossing in fir_crossings.crossings
        ]

    def _build_validation_section(
        self,
        validation: DualValidationResult,
        fir_crossings: FIRIntersectionResult,
    ) -> dict:
        """Build the validation section with dual-system, LLM placeholder, and chain continuity.

        The LLM sanity check is initialized with verdict "pending" — the LLM
        auditor will update it asynchronously after session storage.

        Chain continuity failures come from the FIR intersection engine's
        validation of consecutive exit/entry point gaps.

        Args:
            validation: Dual-system validation result (PostGIS vs Shapely).
            fir_crossings: FIR intersection result with chain continuity data.

        Returns:
            Dict with dual_system, llm_sanity_check, and chain_continuity sections.

        Validates Requirements: 10.1, 12.5
        """
        return {
            "dual_system": {
                "postgis_fir_list": validation.postgis_fir_list,
                "shapely_fir_list": validation.shapely_fir_list,
                "fir_lists_match": validation.fir_lists_match,
                "max_distance_divergence_pct": validation.max_distance_divergence_pct,
                "flagged_for_review": validation.flagged_for_review,
                "per_fir_comparison": validation.per_fir_comparison,
            },
            "llm_sanity_check": {
                "model": None,
                "verdict": "pending",
                "notes": None,
                "anomalies": [],
                "checked_at": None,
            },
            "chain_continuity": {
                "all_valid": len(fir_crossings.chain_continuity_failures) == 0,
                "failures": fir_crossings.chain_continuity_failures,
            },
        }

    def _build_totals(self, charges: list[dict]) -> dict:
        """Calculate totals grouped by currency, total USD/EUR, FIR/country counts.

        Iterates over all charge entries to:
        - Sum charge_amount grouped by currency
        - Sum charge_in_usd for total USD
        - Derive total EUR from USD charges (using the inverse of the
          default EUR→USD rate when no direct EUR total is available)
        - Count distinct FIRs and countries

        Args:
            charges: List of charge dicts from the charge calculator.
                Each dict must have: charge_amount, currency, charge_in_usd,
                country_code (or country).

        Returns:
            Dict with by_currency, total_usd, total_eur, fir_count,
            countries_count.

        Validates Requirements: 10.8
        """
        by_currency: dict[str, float] = {}
        total_usd = 0.0
        total_eur = 0.0
        countries: set[str] = set()

        for charge in charges:
            currency = charge.get("currency", "USD")
            amount = float(charge.get("charge_amount", 0))
            usd_amount = float(charge.get("charge_in_usd", 0))

            # Accumulate by currency
            by_currency[currency] = by_currency.get(currency, 0.0) + amount

            # Accumulate USD total
            total_usd += usd_amount

            # Track unique countries
            country = charge.get("country_code") or charge.get("country", "")
            if country:
                countries.add(country)

        # Derive EUR total: use the EUR bucket if present, otherwise
        # convert from total USD using the default rate
        if "EUR" in by_currency:
            total_eur = by_currency["EUR"]
        elif total_usd > 0:
            from src.services.charge_calculation import DEFAULT_EUR_TO_USD

            total_eur = round(total_usd / DEFAULT_EUR_TO_USD, 2)

        # Round currency buckets
        by_currency = {k: round(v, 2) for k, v in by_currency.items()}

        return {
            "by_currency": by_currency,
            "total_usd": round(total_usd, 2),
            "total_eur": round(total_eur, 2),
            "fir_count": len(charges),
            "countries_count": len(countries),
        }

    def _build_comparison_section(self, input_data: dict) -> dict:
        """Build comparison section with invoice match keys and flown route placeholders.

        Includes invoice match keys derived from input data and placeholder
        fields for future flown route comparison (flown_route_available,
        flown_calculation_id, planned_vs_flown_delta).

        Args:
            input_data: Dict with route parameters from the API request.

        Returns:
            Dict with invoice_match_keys and flown route placeholders.

        Validates Requirements: 10.10, 21.2
        """
        flight_date = input_data.get("flight_date")
        if flight_date is not None and not isinstance(flight_date, str):
            flight_date = str(flight_date)

        return {
            "invoice_match_keys": {
                "flight_number": input_data.get("flight_number"),
                "date": flight_date,
                "origin": input_data.get("origin", ""),
                "destination": input_data.get("destination", ""),
            },
            "flown_route_available": False,
            "flown_calculation_id": None,
            "planned_vs_flown_delta": None,
        }
