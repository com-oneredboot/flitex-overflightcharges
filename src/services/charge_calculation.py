"""Charge calculation interface and default overflight implementation.

This module provides the extensible ChargeCalculationInterface and a default
implementation (DefaultOverflightChargeCalculator) that performs per-FIR
charge calculation using the existing formula registry, eurocontrol unit
rates, and currency conversion.

The interface is designed so that future bilateral agreement logic or
terminal charge calculators can override `calculate_fir_charge` without
modifying the core session builder pipeline.

Validates Requirements: 10.7, 21.1, 21.4, 21.5
"""

import logging
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.formula import Formula
from src.services.fir_intersection_engine import FIRCrossingRecord

logger = logging.getLogger(__name__)

# Fallback EUR→USD rate when no live rate is available
DEFAULT_EUR_TO_USD = 1.10


class ChargeCalculationInterface:
    """Interface for per-FIR charge calculation. Extensible for bilateral agreements.

    Subclass and override `calculate_fir_charge` to insert exemption checks,
    terminal charge logic, or alternative billing rules into the pipeline
    without modifying the core calculation flow.

    Validates Requirements: 21.4
    """

    def calculate_fir_charge(
        self,
        fir_crossing: FIRCrossingRecord,
        aircraft_type: str,
        mtow_kg: float,
        db: Session,
    ) -> dict:
        """Calculate charge for a single FIR crossing. Override for exemptions.

        Args:
            fir_crossing: FIR crossing record with spatial data and distances.
            aircraft_type: Aircraft type code (e.g. "B738").
            mtow_kg: Maximum takeoff weight in kilograms.
            db: SQLAlchemy database session.

        Returns:
            Dict matching the fir_charges JSON schema from the design doc.

        Validates Requirements: 10.7, 21.4
        """
        raise NotImplementedError(
            "Subclasses must implement calculate_fir_charge"
        )


class DefaultOverflightChargeCalculator(ChargeCalculationInterface):
    """Default overflight charge calculator using the formula registry.

    Performs per-FIR charge calculation by:
    1. Looking up the active formula for the FIR's country
    2. Fetching the eurocontrol unit rate for the country
    3. Executing the formula with distance and weight factors
    4. Converting the result to USD using exchange rates

    Each charge entry includes `bilateral_exemption: null` and
    `charge_type: "overflight"` for future extensibility.

    Validates Requirements: 10.7, 21.1, 21.5
    """

    def calculate_fir_charge(
        self,
        fir_crossing: FIRCrossingRecord,
        aircraft_type: str,
        mtow_kg: float,
        db: Session,
    ) -> dict:
        """Calculate overflight charge for a single FIR crossing.

        Looks up the active formula for the FIR's country code, fetches
        the applicable eurocontrol unit rate, executes the formula, and
        builds a charge dict matching the session JSON schema.

        Args:
            fir_crossing: FIR crossing record with spatial/distance data.
            aircraft_type: Aircraft type code.
            mtow_kg: Maximum takeoff weight in kilograms.
            db: SQLAlchemy database session.

        Returns:
            Dict with all fir_charges schema fields including
            bilateral_exemption (null) and charge_type ("overflight").

        Validates Requirements: 10.7, 21.1, 21.5
        """
        country_code = fir_crossing.country_code
        icao_code = fir_crossing.icao_code

        # Step 1: Look up active formula for this FIR's country
        formula = self._lookup_formula(country_code, db)

        # Step 2: Fetch eurocontrol unit rate data for the country
        rate_data = self._fetch_unit_rate(country_code, db)

        # Step 3: Calculate distance and weight factors
        # Use segment distance in nm (standard for overflight charges)
        distance_nm = fir_crossing.segment_distance_nm
        weight_tonnes = mtow_kg / 1000.0

        distance_factor = distance_nm / 100.0
        weight_factor = pow(weight_tonnes / 50.0, 0.5) if weight_tonnes > 0 else 0.0

        # Step 4: Extract unit rate and exchange rate
        unit_rate = 0.0
        unit_rate_source = "eurocontrol_unit_rates"
        unit_rate_effective_date = None
        exchange_rate = 1.0
        exchange_rate_date = None
        currency = "EUR"

        if rate_data:
            unit_rate = rate_data.get("unit_rate", 0.0)
            exchange_rate = rate_data.get("ex_rate_to_eur", 1.0) or 1.0
            currency = rate_data.get("currency", "EUR") or "EUR"
            unit_rate_effective_date = _format_date(
                rate_data.get("date_from")
            )
            exchange_rate_date = _format_date(rate_data.get("date_from"))

        # Step 5: Apply formula or use standard EUROCONTROL calculation
        charge_amount, charge_currency, charge_in_usd, effective_unit_rate = (
            self._execute_charge_formula(
                formula=formula,
                distance_nm=distance_nm,
                weight_tonnes=weight_tonnes,
                distance_factor=distance_factor,
                weight_factor=weight_factor,
                unit_rate=unit_rate,
                exchange_rate=exchange_rate,
                currency=currency,
                rate_data=rate_data,
                fir_crossing=fir_crossing,
            )
        )

        # Use the effective unit rate from the formula/calc if the DB rate was 0
        if effective_unit_rate is not None:
            unit_rate = effective_unit_rate

        # Step 6: Build the justification string
        justification = (
            f"FIR {icao_code} ({fir_crossing.fir_name}): "
            f"distance={distance_nm:.2f}nm, "
            f"weight={weight_tonnes:.1f}t, "
            f"df={distance_factor:.4f}, "
            f"wf={weight_factor:.4f}, "
            f"unit_rate={unit_rate:.2f}, "
            f"charge={charge_amount:.2f} {charge_currency}"
        )

        # Determine formula metadata
        formula_code = formula.formula_code if formula else "NONE"
        formula_version = formula.version_number if formula else 0
        formula_effective_date = (
            str(formula.effective_date) if formula and formula.effective_date else None
        )

        return {
            "icao_code": icao_code,
            "fir_name": fir_crossing.fir_name,
            "country": fir_crossing.country,
            "country_code": country_code,
            "formula_code": formula_code,
            "formula_version": formula_version,
            "formula_effective_date": formula_effective_date,
            "formula_description": formula.description if formula else None,
            "formula_logic": formula.formula_logic if formula else None,
            "unit_rate": unit_rate,
            "unit_rate_source": unit_rate_source,
            "unit_rate_effective_date": unit_rate_effective_date,
            "distance_factor": round(distance_factor, 6),
            "weight_factor": round(weight_factor, 6),
            "charge_amount": round(charge_amount, 2),
            "currency": charge_currency,
            "charge_in_usd": round(charge_in_usd, 2),
            "exchange_rate": exchange_rate,
            "exchange_rate_date": exchange_rate_date,
            "distance_used_km": round(fir_crossing.segment_distance_km, 4),
            "distance_method": "segment",
            "bilateral_exemption": None,
            "charge_type": "overflight",
            "justification": justification,
        }

    def _lookup_formula(
        self, country_code: str, db: Session
    ) -> Formula | None:
        """Look up the active formula for a country code.

        Args:
            country_code: ISO 3166-1 alpha-2 country code.
            db: SQLAlchemy database session.

        Returns:
            Active Formula record or None if not found.
        """
        return (
            db.query(Formula)
            .filter(
                Formula.country_code == country_code,
                Formula.is_active == True,  # noqa: E712
            )
            .first()
        )

    def _fetch_unit_rate(
        self, country_code: str, db: Session
    ) -> dict[str, Any] | None:
        """Fetch the most recent eurocontrol unit rate for a country.

        Queries the eurocontrol_unit_rates table for the latest rate period
        matching the country code.

        Args:
            country_code: ISO 3166-1 alpha-2 country code.
            db: SQLAlchemy database session.

        Returns:
            Dict with unit_rate, ex_rate_to_eur, currency, date_from,
            date_to, country_name — or None if no rate found.
        """
        try:
            # Use a SAVEPOINT so a failure here (e.g. table doesn't exist)
            # does not poison the outer transaction.
            nested = db.begin_nested()
            try:
                result = db.execute(
                    text("""
                        SELECT unit_rate, ex_rate_to_eur, currency,
                               date_from, date_to, country_name
                        FROM eurocontrol_unit_rates
                        WHERE country_code = :cc
                        ORDER BY date_from DESC
                        LIMIT 1
                    """),
                    {"cc": country_code},
                )
                row = result.fetchone()
                nested.commit()
                if row:
                    return {
                        "unit_rate": float(row[0]) if row[0] is not None else 0.0,
                        "ex_rate_to_eur": (
                            float(row[1]) if row[1] is not None else None
                        ),
                        "currency": row[2],
                        "date_from": row[3],
                        "date_to": row[4],
                        "country_name": row[5],
                    }
            except Exception:
                nested.rollback()
                raise
        except Exception as exc:
            logger.warning(
                "Failed to fetch unit rate for %s: %s",
                country_code,
                exc,
            )
        return None

    def _execute_charge_formula(
        self,
        formula: Formula | None,
        distance_nm: float,
        weight_tonnes: float,
        distance_factor: float,
        weight_factor: float,
        unit_rate: float,
        exchange_rate: float,
        currency: str,
        rate_data: dict | None,
        fir_crossing: FIRCrossingRecord,
    ) -> tuple[float, str, float, float | None]:
        """Execute the charge formula and return (amount, currency, usd_amount, effective_unit_rate).

        If a multi-line formula with a `calculate` function exists, it is
        executed with the standard (distance, weight, context) signature.
        Otherwise, the standard EUROCONTROL formula is applied:
            charge = unit_rate * distance_factor * weight_factor

        Args:
            formula: Active Formula record or None.
            distance_nm: Distance through FIR in nautical miles.
            weight_tonnes: Aircraft weight in tonnes.
            distance_factor: distance_nm / 100.
            weight_factor: (weight_tonnes / 50) ^ 0.5.
            unit_rate: Unit rate from eurocontrol_unit_rates (already /100 adjusted by formula or raw).
            exchange_rate: Exchange rate to EUR.
            currency: Billing currency code.
            rate_data: Raw rate data dict or None.
            fir_crossing: The FIR crossing record.

        Returns:
            Tuple of (charge_amount, currency, charge_in_usd, effective_unit_rate).
            effective_unit_rate is the actual rate used by the formula or standard calc.
        """
        charge_amount = 0.0
        charge_currency = currency
        charge_in_usd = 0.0
        effective_unit_rate: float | None = None

        if formula and formula.formula_logic:
            try:
                charge_amount, charge_currency, charge_in_usd, effective_unit_rate = (
                    self._run_formula_logic(
                        formula=formula,
                        distance_nm=distance_nm,
                        weight_tonnes=weight_tonnes,
                        rate_data=rate_data,
                        fir_crossing=fir_crossing,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Formula execution failed for %s (%s), "
                    "falling back to standard calculation: %s",
                    fir_crossing.icao_code,
                    formula.formula_code,
                    exc,
                )
                charge_amount, charge_currency, charge_in_usd, effective_unit_rate = (
                    self._standard_eurocontrol_calc(
                        unit_rate, distance_factor, weight_factor,
                        exchange_rate, currency,
                    )
                )
        else:
            # No formula — use standard EUROCONTROL calculation
            charge_amount, charge_currency, charge_in_usd, effective_unit_rate = (
                self._standard_eurocontrol_calc(
                    unit_rate, distance_factor, weight_factor,
                    exchange_rate, currency,
                )
            )

        return charge_amount, charge_currency, charge_in_usd, effective_unit_rate

    def _run_formula_logic(
        self,
        formula: Formula,
        distance_nm: float,
        weight_tonnes: float,
        rate_data: dict | None,
        fir_crossing: FIRCrossingRecord,
    ) -> tuple[float, str, float, float | None]:
        """Execute a formula's Python logic and extract results.

        Supports multi-line formulas that define a `calculate(distance, weight, context)`
        function, matching the FormulaExecutor pattern.

        Args:
            formula: Formula with formula_logic code.
            distance_nm: Distance in nautical miles.
            weight_tonnes: Weight in tonnes.
            rate_data: Eurocontrol rate data dict.
            fir_crossing: FIR crossing record for context.

        Returns:
            Tuple of (charge_amount, currency, charge_in_usd, effective_unit_rate).
        """
        # Build context dict matching existing formula expectations
        context = {
            "firTag": fir_crossing.icao_code,
            "firName": fir_crossing.fir_name,
            "eurocontrol_rates": {},
        }

        # Populate eurocontrol_rates in the format formulas expect
        if rate_data:
            country_code = fir_crossing.country_code
            context["eurocontrol_rates"] = {
                country_code: {
                    "unit_rate": rate_data.get("unit_rate", 0.0),
                    "ex_rate_to_eur": rate_data.get("ex_rate_to_eur", 1.0),
                    "currency": rate_data.get("currency", "EUR"),
                },
            }

        exec_globals = {
            "__builtins__": {},
            "sqrt": math.sqrt,
            "pow": pow,
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
        }
        exec_locals: dict[str, Any] = {}
        exec(formula.formula_logic, exec_globals, exec_locals)

        calculate_func = exec_locals.get("calculate")
        if calculate_func is None:
            raise ValueError(
                f"Formula {formula.formula_code} does not define calculate()"
            )

        result = calculate_func(distance_nm, weight_tonnes, context)

        if isinstance(result, dict):
            charge_amount = float(result.get("cost", 0))
            charge_currency = result.get("currency", formula.currency or "EUR")
            charge_in_usd = float(result.get("usd_cost", 0))
            effective_unit_rate = float(result["unit_rate"]) if "unit_rate" in result else None
        else:
            charge_amount = float(result)
            charge_currency = formula.currency or "EUR"
            charge_in_usd = charge_amount * DEFAULT_EUR_TO_USD
            effective_unit_rate = None

        return charge_amount, charge_currency, charge_in_usd, effective_unit_rate

    @staticmethod
    def _standard_eurocontrol_calc(
        unit_rate: float,
        distance_factor: float,
        weight_factor: float,
        exchange_rate: float,
        currency: str,
    ) -> tuple[float, str, float, float]:
        """Standard EUROCONTROL charge calculation fallback.

        Formula: euro_cost = unit_rate * distance_factor * weight_factor
                 local_cost = euro_cost * exchange_rate
                 usd_cost = euro_cost * EUR_TO_USD

        Args:
            unit_rate: Unit rate (raw from DB, divided by 100 per EUROCONTROL convention).
            distance_factor: distance_nm / 100.
            weight_factor: (weight_tonnes / 50) ^ 0.5.
            exchange_rate: Exchange rate to local currency from EUR.
            currency: Local billing currency code.

        Returns:
            Tuple of (charge_amount_local, currency, charge_in_usd, adjusted_rate).
        """
        adjusted_rate = unit_rate / 100.0 if unit_rate > 1 else unit_rate
        euro_cost = adjusted_rate * distance_factor * weight_factor
        local_cost = euro_cost * exchange_rate
        usd_cost = euro_cost * DEFAULT_EUR_TO_USD
        return local_cost, currency, usd_cost, adjusted_rate


def _format_date(value: Any) -> str | None:
    """Format a date value to ISO string, or return None."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
