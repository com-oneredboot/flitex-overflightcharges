"""FIR service layer with versioning operations.

This module provides the FIRService class that handles all business logic
for FIR (Flight Information Region) data management with full version
history tracking, soft-delete, and rollback capabilities.

Validates Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.iata_fir import IataFir
from src.schemas.fir import FIRCreate, FIRUpdate
from src.exceptions import FIRNotFoundException, DuplicateFIRException


logger = logging.getLogger(__name__)


class FIRService:
    """Service for managing FIR CRUD operations with versioning.

    This service handles FIR lifecycle including creation, updates with
    automatic versioning, soft-delete, history retrieval, and rollback
    capabilities. All version changes are logged for audit purposes.

    Validates Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8
    """

    def __init__(self, session: Session):
        """Initialize FIRService with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def get_all_active_firs(self) -> List[IataFir]:
        """Retrieve all active FIRs.

        Returns only FIRs where is_active=True, representing the current
        active version for each ICAO code.

        Returns:
            List of active IataFir records

        Validates: Requirement 5.5
        """
        return self.session.query(IataFir).filter(IataFir.is_active == True).all()

    def get_active_fir(self, icao_code: str) -> Optional[IataFir]:
        """Retrieve the single active FIR for an ICAO code.

        Args:
            icao_code: ICAO code (4 uppercase alphanumeric)

        Returns:
            Active IataFir record or None if not found
        """
        return (
            self.session.query(IataFir)
            .filter(IataFir.icao_code == icao_code, IataFir.is_active == True)
            .first()
        )

    def create_fir(self, fir_data: FIRCreate, created_by: str) -> IataFir:
        """Create new FIR with version_number=1, is_active=True, activation_date=now().

        Args:
            fir_data: FIR creation data
            created_by: User identifier for audit trail

        Returns:
            Created IataFir record

        Raises:
            DuplicateFIRException: If an active FIR already exists for the ICAO code

        Validates: Requirements 5.1
        """
        now = datetime.now(timezone.utc)

        new_fir = IataFir(
            icao_code=fir_data.icao_code,
            fir_name=fir_data.fir_name,
            country_code=fir_data.country_code,
            geojson_geometry=fir_data.geojson_geometry,
            bbox_min_lon=fir_data.bbox_min_lon,
            bbox_min_lat=fir_data.bbox_min_lat,
            bbox_max_lon=fir_data.bbox_max_lon,
            bbox_max_lat=fir_data.bbox_max_lat,
            avoid_status=fir_data.avoid_status,
            effective_date=fir_data.effective_date,
            version_number=1,
            is_active=True,
            activation_date=now,
            created_by=created_by,
        )

        try:
            self.session.add(new_fir)
            self.session.commit()
            self.session.refresh(new_fir)

            logger.info(
                f"FIR created for ICAO code {fir_data.icao_code}",
                extra={
                    "icao_code": fir_data.icao_code,
                    "version_number": 1,
                    "created_by": created_by,
                },
            )

            return new_fir
        except IntegrityError as e:
            self.session.rollback()
            raise DuplicateFIRException(
                message=f"FIR with ICAO code '{fir_data.icao_code}' already exists or violates a constraint",
                details={"icao_code": fir_data.icao_code, "error": str(e)},
            )

    def update_fir(self, icao_code: str, fir_data: FIRUpdate, created_by: str) -> IataFir:
        """Update FIR by deactivating current version and creating a new one.

        Deactivates the current active version (is_active=False, deactivation_date=now())
        and creates a new version with version_number+1, is_active=True, activation_date=now().

        Args:
            icao_code: ICAO code of FIR to update
            fir_data: FIR update data (partial updates supported)
            created_by: User identifier for audit trail

        Returns:
            Newly created IataFir version

        Raises:
            FIRNotFoundException: If no active FIR exists for the ICAO code

        Validates: Requirements 5.2
        """
        current_fir = self.get_active_fir(icao_code)
        if not current_fir:
            raise FIRNotFoundException(
                message=f"No active FIR found for ICAO code: {icao_code}",
                details={"icao_code": icao_code},
            )

        now = datetime.now(timezone.utc)

        # Deactivate current version
        current_fir.is_active = False
        current_fir.deactivation_date = now

        # Build new version, carrying forward unchanged fields
        new_version_number = current_fir.version_number + 1
        update_data = fir_data.model_dump(exclude_unset=True)

        new_fir = IataFir(
            icao_code=icao_code,
            fir_name=update_data.get("fir_name", current_fir.fir_name),
            country_code=current_fir.country_code,
            geojson_geometry=update_data.get("geojson_geometry", current_fir.geojson_geometry),
            bbox_min_lon=update_data.get("bbox_min_lon", current_fir.bbox_min_lon),
            bbox_min_lat=update_data.get("bbox_min_lat", current_fir.bbox_min_lat),
            bbox_max_lon=update_data.get("bbox_max_lon", current_fir.bbox_max_lon),
            bbox_max_lat=update_data.get("bbox_max_lat", current_fir.bbox_max_lat),
            avoid_status=update_data.get("avoid_status", current_fir.avoid_status),
            effective_date=update_data.get("effective_date", current_fir.effective_date),
            version_number=new_version_number,
            is_active=True,
            activation_date=now,
            created_by=created_by,
        )

        try:
            self.session.add(new_fir)
            self.session.commit()
            self.session.refresh(new_fir)

            logger.info(
                f"FIR updated for ICAO code {icao_code}",
                extra={
                    "icao_code": icao_code,
                    "version_number": new_version_number,
                    "created_by": created_by,
                    "previous_version": current_fir.version_number,
                },
            )

            return new_fir
        except IntegrityError as e:
            self.session.rollback()
            raise DuplicateFIRException(
                message=f"FIR update failed for ICAO code '{icao_code}'",
                details={"icao_code": icao_code, "error": str(e)},
            )

    def soft_delete_fir(self, icao_code: str) -> bool:
        """Soft-delete FIR by setting is_active=False and deactivation_date=now().

        No physical row removal — preserves audit history and enables rollback.

        Args:
            icao_code: ICAO code of FIR to soft-delete

        Returns:
            True if FIR was soft-deleted

        Raises:
            FIRNotFoundException: If no active FIR exists for the ICAO code

        Validates: Requirements 5.3
        """
        current_fir = self.get_active_fir(icao_code)
        if not current_fir:
            raise FIRNotFoundException(
                message=f"No active FIR found for ICAO code: {icao_code}",
                details={"icao_code": icao_code},
            )

        now = datetime.now(timezone.utc)
        current_fir.is_active = False
        current_fir.deactivation_date = now

        self.session.commit()

        logger.info(
            f"FIR soft-deleted for ICAO code {icao_code}",
            extra={
                "icao_code": icao_code,
                "version_number": current_fir.version_number,
            },
        )

        return True

    def get_fir_history(self, icao_code: str) -> List[IataFir]:
        """Retrieve all FIR versions for an ICAO code ordered by version_number DESC.

        Args:
            icao_code: ICAO code to retrieve history for

        Returns:
            List of IataFir records ordered by version_number descending

        Raises:
            FIRNotFoundException: If no versions exist for the ICAO code

        Validates: Requirements 5.6
        """
        firs = (
            self.session.query(IataFir)
            .filter(IataFir.icao_code == icao_code)
            .order_by(IataFir.version_number.desc())
            .all()
        )

        if not firs:
            raise FIRNotFoundException(
                message=f"No FIR history found for ICAO code: {icao_code}",
                details={"icao_code": icao_code},
            )

        return firs

    def rollback_fir(self, icao_code: str, version_number: int) -> IataFir:
        """Rollback to a specified FIR version.

        Deactivates the current active version and reactivates the target version
        (is_active=True, deactivation_date=None, activation_date=now()).

        Args:
            icao_code: ICAO code of FIR to rollback
            version_number: Version number to rollback to

        Returns:
            Reactivated IataFir version

        Raises:
            FIRNotFoundException: If no active FIR exists or target version not found

        Validates: Requirements 5.4
        """
        # Get current active FIR
        current_fir = self.get_active_fir(icao_code)
        if not current_fir:
            raise FIRNotFoundException(
                message=f"No active FIR found for ICAO code: {icao_code}",
                details={"icao_code": icao_code},
            )

        # Get target version
        target_fir = (
            self.session.query(IataFir)
            .filter(
                IataFir.icao_code == icao_code,
                IataFir.version_number == version_number,
            )
            .first()
        )

        if not target_fir:
            raise FIRNotFoundException(
                message=f"FIR version {version_number} not found for ICAO code: {icao_code}",
                details={"icao_code": icao_code, "version_number": version_number},
            )

        now = datetime.now(timezone.utc)

        # Deactivate current version first and flush to satisfy the partial
        # unique index (only one active FIR per ICAO code) before reactivating
        # the target version.
        current_fir.is_active = False
        current_fir.deactivation_date = now
        self.session.flush()

        # Reactivate target version
        target_fir.is_active = True
        target_fir.deactivation_date = None
        target_fir.activation_date = now

        self.session.commit()
        self.session.refresh(target_fir)

        logger.info(
            f"FIR rolled back for ICAO code {icao_code}",
            extra={
                "icao_code": icao_code,
                "version_number": version_number,
                "previous_version": current_fir.version_number,
            },
        )

        return target_fir
