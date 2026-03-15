"""CostCalculator service for overflight charge calculations.

This module provides the CostCalculator class that orchestrates the full
calculation flow: parsing routes, identifying FIR crossings, retrieving formulas,
executing them, and storing results with full audit trail.

Validates Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.10, 6.1, 6.2, 6.3, 6.4
"""

import logging
import math
from typing import List
from decimal import Decimal
from sqlalchemy.orm import Session

from src.services.route_parser import RouteParser, Waypoint
from src.services.fir_service import FIRService
from src.services.formula_service import FormulaService
from src.models.route_calculation import RouteCalculation
from src.models.fir_charge import FirCharge
from src.models.iata_fir import IataFir
from src.models.formula import Formula
from src.schemas.route_cost import RouteCostResponse, FIRChargeBreakdown, FIRWarning
from src.exceptions import ParsingException, ValidationException


logger = logging.getLogger(__name__)


class CostCalculator:
    """Service for calculating overflight charges.
    
    This service orchestrates the complete calculation flow:
    1. Parse ICAO route string into waypoints
    2. Identify FIR crossings along the route
    3. Retrieve active formulas for each FIR country
    4. Execute formulas to calculate charges
    5. Store calculation record and per-FIR breakdown
    
    Validates Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.10, 6.1, 6.2, 6.3, 6.4
    """
    
    def __init__(self, session: Session):
        """Initialize CostCalculator with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.route_parser = RouteParser()
        self.fir_service = FIRService(session)
        self.formula_service = FormulaService(session)
    
    def calculate_route_cost(
        self,
        route_string: str,
        origin: str,
        destination: str,
        aircraft_type: str,
        mtow_kg: float
    ) -> RouteCostResponse:
        """Calculate total overflight charges for route.
        
        Orchestrates the full calculation flow:
        - Parses route string into waypoints
        - Identifies FIR crossings
        - Retrieves active formulas for each FIR
        - Calculates charges using formulas
        - Stores calculation record and breakdown
        
        Args:
            route_string: ICAO route format
            origin: Origin airport code
            destination: Destination airport code
            aircraft_type: Aircraft type code
            mtow_kg: Maximum takeoff weight in kilograms
        
        Returns:
            RouteCostResponse with total cost and FIR breakdown
        
        Raises:
            ParsingException: If route parsing fails
            ValidationException: If calculation fails
        
        Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.4
        """
        logger.info(
            f"Starting route cost calculation",
            extra={
                "route_string": route_string,
                "origin": origin,
                "destination": destination,
                "aircraft_type": aircraft_type,
                "mtow_kg": mtow_kg
            }
        )
        
        # Step 1: Parse route string into waypoints (Requirement 5.3)
        try:
            waypoints = self.route_parser.parse_route(route_string, self.session)
            logger.debug(
                f"Parsed route into {len(waypoints)} waypoints",
                extra={"waypoints_count": len(waypoints)}
            )
        except ParsingException as e:
            logger.error(
                f"Route parsing failed: {e.message}",
                extra={"route_string": route_string, "error": e.message}
            )
            raise
        
        # Step 2 & 3: Identify FIR crossings via PostGIS spatial query (Requirement 5.4)
        fir_crossings = self.route_parser.identify_fir_crossings_db(waypoints, self.session)
        fir_codes = [fc.icao_code for fc in fir_crossings]
        logger.info(
            f"Identified {len(fir_codes)} FIR crossings",
            extra={"fir_crossings": fir_codes}
        )
        
        # Step 4: Calculate charges for each FIR crossing
        fir_breakdown: List[FIRChargeBreakdown] = []
        total_cost = Decimal("0.00")
        currency = "USD"  # Default currency
        
        for fir_code in fir_codes:
            # Get FIR details
            fir = self.fir_service.get_active_fir(fir_code)
            if not fir:
                logger.warning(
                    f"FIR not found for code {fir_code}, skipping",
                    extra={"fir_code": fir_code}
                )
                continue
            
            # Get active formula for FIR country (Requirement 5.5)
            formula = self.formula_service.get_active_formula(fir.country_code)
            
            if not formula:
                # Include FIR with warning instead of silently skipping (Requirement 2.3)
                logger.warning(
                    f"No active formula found for country {fir.country_code}, including FIR {fir_code} with warning",
                    extra={
                        "fir_code": fir_code,
                        "country_code": fir.country_code
                    }
                )
                fir_breakdown.append(FIRChargeBreakdown(
                    icao_code=fir.icao_code,
                    fir_id=fir.id,
                    fir_name=fir.fir_name,
                    country_code=fir.country_code,
                    charge_amount=Decimal("0"),
                    currency="N/A",
                    formula_code="NONE",
                    warning=FIRWarning(
                        message=f"No active formula for country {fir.country_code}",
                        detail=f"FIR: {fir_code}, Country: {fir.country_code} — no active formula found in database"
                    )
                ))
                continue
            
            # Calculate distance through FIR (simplified - using fixed distance)
            # In production, this would calculate actual distance through FIR geometry
            distance_km = 100.0  # Placeholder distance
            
            # Apply formula to calculate charge (Requirement 5.6)
            try:
                charge_amount = self.apply_formula(formula, mtow_kg, distance_km)
                
                # Use formula currency
                currency = formula.currency
                
                # Add to breakdown
                fir_breakdown.append(FIRChargeBreakdown(
                    icao_code=fir.icao_code,
                    fir_id=fir.id,
                    fir_name=fir.fir_name,
                    country_code=fir.country_code,
                    charge_amount=charge_amount,
                    currency=currency,
                    formula_code=formula.formula_code,
                    formula_version=formula.version_number,
                    formula_description=formula.description,
                    formula_logic=formula.formula_logic,
                    effective_date=str(formula.effective_date)
                ))
                
                # Add to total (Requirement 5.7)
                total_cost += charge_amount
                
                logger.debug(
                    f"Calculated charge for FIR {fir_code}",
                    extra={
                        "fir_code": fir_code,
                        "charge_amount": float(charge_amount),
                        "currency": currency
                    }
                )
            
            except Exception as e:
                logger.error(
                    f"Failed to calculate charge for FIR {fir_code}: {str(e)}",
                    extra={
                        "fir_code": fir_code,
                        "country_code": fir.country_code,
                        "error": str(e)
                    }
                )
                # Include FIR with warning instead of silently skipping (Requirement 2.2)
                error_type = type(e).__name__
                fir_breakdown.append(FIRChargeBreakdown(
                    icao_code=fir.icao_code,
                    fir_id=fir.id,
                    fir_name=fir.fir_name,
                    country_code=fir.country_code,
                    charge_amount=Decimal("0"),
                    currency=formula.currency,
                    formula_code=formula.formula_code,
                    formula_version=formula.version_number,
                    formula_description=formula.description,
                    formula_logic=formula.formula_logic,
                    effective_date=str(formula.effective_date) if formula.effective_date else None,
                    warning=FIRWarning(
                        message=f"Formula execution failed for {fir_code}",
                        detail=f"FIR: {fir_code}, Country: {fir.country_code}, Formula: {formula.formula_code}, Error: {error_type}: {str(e)}"
                    )
                ))
                continue
        
        # Step 5: Store calculation record (Requirement 6.1, 6.2)
        calculation_record = RouteCalculation(
            route_string=route_string,
            origin=origin,
            destination=destination,
            aircraft_type=aircraft_type,
            mtow_kg=Decimal(str(mtow_kg)),
            total_cost=total_cost,
            currency=currency
        )
        
        self.session.add(calculation_record)
        self.session.flush()  # Get the calculation_id
        
        # Step 6: Store per-FIR breakdown (Requirement 6.3, 6.4)
        for breakdown in fir_breakdown:
            fir_charge = FirCharge(
                calculation_id=calculation_record.id,
                fir_id=breakdown.fir_id,
                icao_code=breakdown.icao_code,
                fir_name=breakdown.fir_name,
                country_code=breakdown.country_code,
                charge_amount=breakdown.charge_amount,
                currency=breakdown.currency
            )
            self.session.add(fir_charge)
        
        # Commit transaction
        self.session.commit()
        self.session.refresh(calculation_record)
        
        logger.info(
            f"Route cost calculation completed",
            extra={
                "calculation_id": str(calculation_record.id),
                "total_cost": float(total_cost),
                "currency": currency,
                "fir_count": len(fir_breakdown)
            }
        )
        
        # Return response
        return RouteCostResponse(
            calculation_id=calculation_record.id,
            total_cost=total_cost,
            currency=currency,
            fir_breakdown=fir_breakdown
        )
    
    def apply_formula(
        self,
        formula: Formula,
        mtow_kg: float,
        distance_km: float
    ) -> Decimal:
        """Apply country formula to calculate charge.

        Executes the Python formula logic with mtow_kg and distance_km
        as input variables. The formula should return a numeric value
        representing the charge amount.

        Supports two formula formats:
        - Single-line expressions: evaluated via eval() (e.g., "mtow_kg * 0.5 + distance_km * 2.0")
        - Multi-line function definitions: executed via exec() then calling calculate()
          (e.g., "def calculate(distance, weight, context):\\n    return distance * weight * 0.01")

        Args:
            formula: Formula object with Python logic
            mtow_kg: Maximum takeoff weight in kilograms
            distance_km: Distance through FIR in kilometers

        Returns:
            Calculated charge amount as Decimal

        Raises:
            ValidationException: If formula execution fails

        Validates: Requirement 5.6, 2.1, 3.1

        Example:
            >>> formula = Formula(formula_logic="mtow_kg * 0.5 + distance_km * 2.0")
            >>> charge = calculator.apply_formula(formula, 50000.0, 100.0)
            >>> charge
            Decimal('25200.00')
        """
        try:
            is_multiline = "def " in formula.formula_logic or "\n" in formula.formula_logic

            if is_multiline:
                # Multi-line formula: use exec() to define the function,
                # then call calculate() — mirrors FormulaExecutor.execute_formula() pattern
                exec_globals = {
                    "__builtins__": {},
                    "sqrt": math.sqrt,
                    "pow": pow,
                    "abs": abs,
                    "min": min,
                    "max": max,
                    "round": round,
                }
                exec_locals = {}
                exec(formula.formula_logic, exec_globals, exec_locals)

                calculate_func = exec_locals["calculate"]
                # Formulas define calculate(distance, weight, context)
                # Pass mtow_kg as distance, distance_km as weight, and an empty context dict
                result = calculate_func(mtow_kg, distance_km, {})

                # Multi-line formulas return a dict {'cost': ..., 'currency': ..., 'usd_cost': ...}
                # Extract the numeric cost value from the dict
                if isinstance(result, dict):
                    result = result.get("cost", 0)
            else:
                # Single-line expression: keep existing eval() path unchanged (preservation)
                context = {
                    "mtow_kg": mtow_kg,
                    "distance_km": distance_km,
                    # Add common math functions for formula use
                    "sqrt": math.sqrt,
                    "pow": pow,
                    "min": min,
                    "max": max,
                    "abs": abs,
                    "round": round,
                }
                result = eval(formula.formula_logic, {"__builtins__": {}}, context)

            # Convert result to Decimal for precision
            charge_amount = Decimal(str(result))

            # Ensure non-negative charge
            if charge_amount < 0:
                logger.warning(
                    f"Formula produced negative charge, setting to 0",
                    extra={
                        "country_code": formula.country_code,
                        "calculated_charge": float(charge_amount)
                    }
                )
                charge_amount = Decimal("0.00")

            return charge_amount

        except Exception as e:
            raise ValidationException(
                message=f"Formula execution failed: {str(e)}",
                details={
                    "country_code": formula.country_code,
                    "formula_code": formula.formula_code,
                    "error": str(e)
                }
            )
