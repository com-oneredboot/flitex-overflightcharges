"""Formula service for CRUD operations with versioning logic.

This module provides the FormulaService class for managing country-specific
overflight charge formulas with version history tracking and rollback capabilities.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.formula import Formula
from src.schemas.formula import FormulaCreate, FormulaUpdate
from src.exceptions import FormulaNotFoundException, ValidationException
from src.services.formula_parser import FormulaParser


logger = logging.getLogger(__name__)


class FormulaService:
    """Service for managing formula CRUD operations with versioning.
    
    This service handles formula lifecycle including creation, updates with
    automatic versioning, deletion, history retrieval, and rollback capabilities.
    All version changes are logged for audit purposes.
    
    Validates Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8, 3.9,
                           21.1, 21.2, 21.3, 21.4, 21.6, 21.8, 21.9, 21.11
    """
    
    def __init__(self, session: Session):
        """Initialize FormulaService with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.parser = FormulaParser()
    
    def get_all_active_formulas(self) -> List[Formula]:
        """Retrieve all active formulas.
        
        Returns only formulas where is_active=true, representing the current
        active version for each country.
        
        Returns:
            List of active Formula records
        
        Validates: Requirement 3.1
        """
        return self.session.query(Formula).filter(Formula.is_active == True).all()
    
    def get_active_formula(self, country_code: str) -> Optional[Formula]:
        """Retrieve active formula for a specific country.
        
        Returns the single active formula version for the given country code.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
        
        Returns:
            Active Formula record or None if not found
        
        Validates: Requirement 3.2
        """
        return (
            self.session.query(Formula)
            .filter(Formula.country_code == country_code, Formula.is_active == True)
            .first()
        )

    def get_formulas_by_description(self, description: str) -> List[Formula]:
        """Retrieve all formulas matching a specific description.

        Returns all formula versions (active and inactive) that match the
        given description exactly.

        Args:
            description: Description to search for (exact match)

        Returns:
            List of Formula records matching the description

        Validates: Requirement 6.2
        """
        return (
            self.session.query(Formula)
            .filter(Formula.description == description)
            .all()
        )

    def get_regional_formulas(self) -> List[Formula]:
        """Retrieve all regional formulas (country_code IS NULL).

        Returns all formula versions where country_code is NULL, representing
        regional formulas like EuroControl and Oceanic.

        Returns:
            List of regional Formula records

        Validates: Requirement 6.3, 6.4
        """
        return (
            self.session.query(Formula)
            .filter(Formula.country_code.is_(None))
            .all()
        )

    def get_country_formulas(self) -> List[Formula]:
        """Retrieve all country-specific formulas (country_code IS NOT NULL).

        Returns all formula versions where country_code is not NULL, representing
        country-specific formulas.

        Returns:
            List of country-specific Formula records

        Validates: Requirement 6.4
        """
        return (
            self.session.query(Formula)
            .filter(Formula.country_code.isnot(None))
            .all()
        )

    
    def create_formula(self, formula_data: FormulaCreate, created_by: str) -> Formula:
        """Create new formula with version_number=1 and is_active=true.
        
        Validates formula syntax before creation. Sets initial version to 1
        and marks as active.
        
        Args:
            formula_data: Formula creation data
            created_by: User identifier for audit trail
        
        Returns:
            Created Formula record
        
        Raises:
            ValidationException: If formula syntax is invalid
        
        Validates: Requirements 3.3, 21.1, 21.11
        """
        # Validate formula syntax
        is_valid, error_message = self.validate_formula_syntax(formula_data.formula_logic)
        if not is_valid:
            raise ValidationException(
                message=f"Invalid formula syntax: {error_message}"
            )
        
        # Create new formula with version 1
        new_formula = Formula(
            country_code=formula_data.country_code,
            description=formula_data.description,
            formula_code=formula_data.formula_code,
            formula_logic=formula_data.formula_logic,
            effective_date=formula_data.effective_date,
            currency=formula_data.currency,
            version_number=1,
            is_active=True,
            created_by=created_by,
            activation_date=datetime.now(timezone.utc)
        )
        
        try:
            self.session.add(new_formula)
            self.session.commit()
            self.session.refresh(new_formula)
            
            # Log formula creation for audit
            logger.info(
                f"Formula created for country {formula_data.country_code}",
                extra={
                    "country_code": formula_data.country_code,
                    "version_number": 1,
                    "created_by": created_by
                }
            )
            
            return new_formula
        except IntegrityError as e:
            self.session.rollback()
            raise ValidationException(
                message=f"Formula creation failed: {str(e)}"
            )
    
    def update_formula(
        self,
        country_code: str,
        formula_data: FormulaUpdate,
        created_by: str
    ) -> Formula:
        """Update formula by creating new version and deactivating current.
        
        Deactivates the current active version and creates a new version with
        incremented version_number. Ensures exactly one active version per country.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
            formula_data: Formula update data
            created_by: User identifier for audit trail
        
        Returns:
            Newly created Formula version
        
        Raises:
            FormulaNotFoundException: If no active formula exists for country
            ValidationException: If formula syntax is invalid
        
        Validates: Requirements 3.4, 21.2, 21.3, 21.11
        """
        # Get current active formula
        current_formula = self.get_active_formula(country_code)
        if not current_formula:
            raise FormulaNotFoundException(
                message=f"No active formula found for country code: {country_code}"
            )
        
        # Validate formula syntax if formula_logic is being updated
        if formula_data.formula_logic:
            is_valid, error_message = self.validate_formula_syntax(formula_data.formula_logic)
            if not is_valid:
                raise ValidationException(
                    message=f"Invalid formula syntax: {error_message}"
                )
        
        # Deactivate current version
        current_formula.is_active = False
        current_formula.deactivation_date = datetime.now(timezone.utc)
        
        # Create new version with incremented version_number
        new_version_number = current_formula.version_number + 1
        new_formula = Formula(
            country_code=country_code,
            description=formula_data.description or current_formula.description,
            formula_code=formula_data.formula_code or current_formula.formula_code,
            formula_logic=formula_data.formula_logic or current_formula.formula_logic,
            effective_date=formula_data.effective_date or current_formula.effective_date,
            currency=formula_data.currency or current_formula.currency,
            version_number=new_version_number,
            is_active=True,
            created_by=created_by,
            activation_date=datetime.now(timezone.utc)
        )
        
        try:
            self.session.add(new_formula)
            self.session.commit()
            self.session.refresh(new_formula)
            
            # Log formula update for audit
            logger.info(
                f"Formula updated for country {country_code}",
                extra={
                    "country_code": country_code,
                    "version_number": new_version_number,
                    "created_by": created_by,
                    "previous_version": current_formula.version_number
                }
            )
            
            return new_formula
        except IntegrityError as e:
            self.session.rollback()
            raise ValidationException(
                message=f"Formula update failed: {str(e)}"
            )
    
    def delete_formula(self, country_code: str) -> bool:
        """Delete all formula versions for a country.
        
        Removes all version records for the specified country code.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
        
        Returns:
            True if formulas were deleted
        
        Raises:
            FormulaNotFoundException: If no formulas exist for country
        
        Validates: Requirement 3.5
        """
        # Get all versions for country
        formulas = (
            self.session.query(Formula)
            .filter(Formula.country_code == country_code)
            .all()
        )
        
        if not formulas:
            raise FormulaNotFoundException(
                message=f"No formulas found for country code: {country_code}"
            )
        
        # Delete all versions
        for formula in formulas:
            self.session.delete(formula)
        
        self.session.commit()
        
        # Log formula deletion for audit
        logger.info(
            f"All formula versions deleted for country {country_code}",
            extra={
                "country_code": country_code,
                "versions_deleted": len(formulas)
            }
        )
        
        return True
    
    def get_formula_history(self, country_code: str) -> List[Formula]:
        """Retrieve all formula versions for a country ordered by version DESC.
        
        Returns complete version history for the specified country, with most
        recent version first.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
        
        Returns:
            List of Formula records ordered by version_number descending
        
        Raises:
            FormulaNotFoundException: If no formulas exist for country
        
        Validates: Requirements 3.7, 21.6
        """
        formulas = (
            self.session.query(Formula)
            .filter(Formula.country_code == country_code)
            .order_by(Formula.version_number.desc())
            .all()
        )
        
        if not formulas:
            raise FormulaNotFoundException(
                message=f"No formula history found for country code: {country_code}"
            )
        
        return formulas
    
    def rollback_formula(self, country_code: str, version_number: int) -> Formula:
        """Rollback to a specified formula version.
        
        Deactivates the current active version and activates the specified
        version number. The specified version must exist for the country.
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
            version_number: Version number to rollback to
        
        Returns:
            Activated Formula version
        
        Raises:
            FormulaNotFoundException: If specified version doesn't exist
        
        Validates: Requirements 3.8, 21.8, 21.11
        """
        # Get current active formula
        current_formula = self.get_active_formula(country_code)
        if not current_formula:
            raise FormulaNotFoundException(
                message=f"No active formula found for country code: {country_code}"
            )
        
        # Get target version to rollback to
        target_formula = (
            self.session.query(Formula)
            .filter(
                Formula.country_code == country_code,
                Formula.version_number == version_number
            )
            .first()
        )
        
        if not target_formula:
            raise FormulaNotFoundException(
                message=f"Formula version {version_number} not found for country code: {country_code}"
            )
        
        # Deactivate current version
        current_formula.is_active = False
        current_formula.deactivation_date = datetime.now(timezone.utc)
        
        # Activate target version
        target_formula.is_active = True
        target_formula.activation_date = datetime.now(timezone.utc)
        
        self.session.commit()
        self.session.refresh(target_formula)
        
        # Log formula rollback for audit
        logger.info(
            f"Formula rolled back for country {country_code}",
            extra={
                "country_code": country_code,
                "version_number": version_number,
                "previous_version": current_formula.version_number
            }
        )
        
        return target_formula
    
    def validate_formula_syntax(self, formula_logic: str) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax of formula logic.
        
        Uses FormulaParser to validate that the formula logic is valid Python
        code without executing it.
        
        Args:
            formula_logic: Python code as string
        
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if syntax is valid, False otherwise
            - error_message: None if valid, descriptive error message if invalid
        
        Validates: Requirement 3.9
        """
        return self.parser.validate_syntax(formula_logic)
