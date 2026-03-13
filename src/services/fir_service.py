"""FIR service layer for CRUD operations.

This module provides the FIRService class that handles all business logic
for FIR (Flight Information Region) data management.

Validates Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 1.8
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.iata_fir import IataFir
from src.schemas.fir import FIRCreate, FIRUpdate
from src.exceptions import FIRNotFoundException, DuplicateFIRException


class FIRService:
    """
    Service class for FIR CRUD operations.
    
    Provides methods to create, read, update, and delete FIR records,
    as well as query FIRs by country code.
    """
    
    def __init__(self, session: Session):
        """
        Initialize the FIR service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
    
    def get_all_firs(self) -> List[IataFir]:
        """
        Retrieve all FIR records.
        
        Validates Requirement: 1.1
        
        Returns:
            List of all IataFir records
        """
        return self.session.query(IataFir).all()
    
    def get_fir_by_code(self, icao_code: str) -> Optional[IataFir]:
        """
        Retrieve FIR by ICAO code.
        
        Validates Requirement: 1.2
        
        Args:
            icao_code: ICAO code (4 uppercase alphanumeric)
        
        Returns:
            IataFir record if found, None otherwise
        """
        return self.session.query(IataFir).filter(
            IataFir.icao_code == icao_code
        ).first()
    
    def create_fir(self, fir_data: FIRCreate) -> IataFir:
        """
        Create new FIR record.
        
        Validates Requirements: 1.3, 1.6, 1.8
        
        Args:
            fir_data: FIR creation data
        
        Returns:
            Created IataFir record
        
        Raises:
            DuplicateFIRException: If FIR with icao_code already exists
        """
        # Check if FIR already exists
        existing_fir = self.get_fir_by_code(fir_data.icao_code)
        if existing_fir:
            raise DuplicateFIRException(
                message=f"FIR with ICAO code '{fir_data.icao_code}' already exists",
                details={"icao_code": fir_data.icao_code}
            )
        
        # Create new FIR record
        fir = IataFir(
            icao_code=fir_data.icao_code,
            fir_name=fir_data.fir_name,
            country_code=fir_data.country_code,
            country_name=fir_data.country_name,
            geojson_geometry=fir_data.geojson_geometry,
            bbox_min_lon=fir_data.bbox_min_lon,
            bbox_min_lat=fir_data.bbox_min_lat,
            bbox_max_lon=fir_data.bbox_max_lon,
            bbox_max_lat=fir_data.bbox_max_lat,
            avoid_status=fir_data.avoid_status
        )
        
        try:
            self.session.add(fir)
            self.session.commit()
            self.session.refresh(fir)
            return fir
        except IntegrityError as e:
            self.session.rollback()
            raise DuplicateFIRException(
                message=f"FIR with ICAO code '{fir_data.icao_code}' already exists",
                details={"icao_code": fir_data.icao_code, "error": str(e)}
            )
    
    def update_fir(self, icao_code: str, fir_data: FIRUpdate) -> IataFir:
        """
        Update existing FIR record.
        
        Validates Requirements: 1.4, 1.7
        
        Args:
            icao_code: ICAO code of FIR to update
            fir_data: FIR update data (partial updates supported)
        
        Returns:
            Updated IataFir record
        
        Raises:
            FIRNotFoundException: If FIR with icao_code does not exist
        """
        # Retrieve existing FIR
        fir = self.get_fir_by_code(icao_code)
        if not fir:
            raise FIRNotFoundException(
                message=f"FIR with ICAO code '{icao_code}' not found",
                details={"icao_code": icao_code}
            )
        
        # Update fields if provided
        update_data = fir_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(fir, field, value)
        
        self.session.commit()
        self.session.refresh(fir)
        return fir
    
    def delete_fir(self, icao_code: str) -> bool:
        """
        Delete FIR record.
        
        Validates Requirements: 1.5, 1.7
        
        Args:
            icao_code: ICAO code of FIR to delete
        
        Returns:
            True if FIR was deleted
        
        Raises:
            FIRNotFoundException: If FIR with icao_code does not exist
        """
        # Retrieve existing FIR
        fir = self.get_fir_by_code(icao_code)
        if not fir:
            raise FIRNotFoundException(
                message=f"FIR with ICAO code '{icao_code}' not found",
                details={"icao_code": icao_code}
            )
        
        self.session.delete(fir)
        self.session.commit()
        return True
    
    def get_firs_by_country(self, country_code: str) -> List[IataFir]:
        """
        Retrieve all FIRs for a country.
        
        Uses indexed query for performance (Requirement 22.2).
        
        Args:
            country_code: ISO 3166-1 alpha-2 country code
        
        Returns:
            List of IataFir records for the specified country
        """
        return self.session.query(IataFir).filter(
            IataFir.country_code == country_code
        ).all()
