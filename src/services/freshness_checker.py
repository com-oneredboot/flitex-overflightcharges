"""Freshness Checker for EUROCONTROL unit rate data and FIR boundary versioning.

Provides an API-facing service that:
- Compares the latest locally stored EUROCONTROL unit rate month against
  the most recent available month to detect stale data.
- Derives the current AIRAC cycle identifier from the date.
- Reports FIR boundary summary (total count, latest update).
- Imports new FIR boundary data as a new version row without overwriting
  existing versions, preserving historical calculation validity.

Validates Requirements: 15.1, 15.2, 15.3, 15.4
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.models.iata_fir import IataFir

logger = logging.getLogger(__name__)

# AIRAC reference: cycle 2401 started on 2024-01-25.
# Each cycle is exactly 28 days.
_AIRAC_REF_DATE = date(2024, 1, 25)
_AIRAC_REF_YEAR = 24
_AIRAC_REF_SEQ = 1
_AIRAC_CYCLE_DAYS = 28


def airac_cycle_for_date(ref_date: date | None = None) -> dict[str, str]:
    """Derive the AIRAC cycle identifier for a given date.

    Uses a known reference point (cycle 2401 = 2024-01-25) and counts
    28-day intervals forward or backward.  The identifier format is
    ``YYNN`` — two-digit year plus two-digit sequence (01–13).

    Returns:
        ``{"current_cycle": "2407", "effective_date": "2024-07-18"}``
    """
    if ref_date is None:
        ref_date = date.today()

    days_offset = (ref_date - _AIRAC_REF_DATE).days
    cycle_offset = days_offset // _AIRAC_CYCLE_DAYS  # can be negative

    # Effective date of the cycle containing ref_date
    effective = _AIRAC_REF_DATE + timedelta(days=cycle_offset * _AIRAC_CYCLE_DAYS)

    # Convert offset to year + sequence (1-based, 13 cycles per year)
    # Absolute cycle number from reference (ref = year 24, seq 1 → index 0)
    abs_index = cycle_offset  # 0 = ref cycle
    # Total cycles from year 00 seq 01 for the reference
    ref_total = _AIRAC_REF_YEAR * 13 + (_AIRAC_REF_SEQ - 1)
    total = ref_total + abs_index

    if total < 0:
        # Before year 2000 — clamp
        total = 0

    year = (total // 13) % 100
    seq = (total % 13) + 1  # 1-based

    return {
        "current_cycle": f"{year:02d}{seq:02d}",
        "effective_date": effective.isoformat(),
    }


class FreshnessChecker:
    """Service for checking data freshness and importing FIR versions.

    Validates Requirements: 15.1, 15.2, 15.3, 15.4
    """

    def check_freshness(self, db: Session) -> dict[str, Any]:
        """Compare latest EUROCONTROL unit rate month vs local data.

        Queries the ``eurocontrol_unit_rates`` table for the most recent
        ``date_to`` value, compares it against the current date to
        determine staleness, and includes the current AIRAC cycle
        identifier and FIR boundary summary.

        Args:
            db: Active SQLAlchemy session.

        Returns:
            Response dict matching the design's expected structure::

                {
                    "unit_rates": {
                        "latest_local_month": "2024-07",
                        "is_stale": true/false,
                        "source": "EUROCONTROL"
                    },
                    "airac_cycle": {
                        "current_cycle": "2407",
                        "effective_date": "2024-07-18"
                    },
                    "fir_boundaries": {
                        "total_count": 245,
                        "latest_update": "2024-03-15T10:00:00Z"
                    }
                }

        Validates Requirements: 15.1, 15.2, 15.3
        """
        unit_rates_info = self._query_unit_rates(db)
        airac_info = airac_cycle_for_date()
        fir_info = self._query_fir_boundaries(db)

        return {
            "unit_rates": unit_rates_info,
            "airac_cycle": airac_info,
            "fir_boundaries": fir_info,
        }

    def import_fir_version(self, fir_data: dict, db: Session) -> None:
        """Import new FIR boundary data as a new version row.

        Creates a new ``IataFir`` record with an incremented
        ``version_number`` for the given ICAO code.  The previous
        active version is deactivated (``is_active=False``,
        ``deactivation_date`` set) so that only one version is active
        per ICAO code at any time, while all historical versions are
        preserved for audit.

        Args:
            fir_data: Dict with keys ``icao_code``, ``fir_name``,
                ``country_code``, ``geojson_geometry``, and optionally
                ``effective_date``, ``created_by``, ``bbox_min_lon``,
                ``bbox_min_lat``, ``bbox_max_lon``, ``bbox_max_lat``,
                ``avoid_status``.
            db: Active SQLAlchemy session.  Caller is responsible for
                committing.

        Validates Requirements: 15.4
        """
        icao_code = fir_data["icao_code"]

        # Determine next version number for this ICAO code.
        max_version = (
            db.query(func.max(IataFir.version_number))
            .filter(IataFir.icao_code == icao_code)
            .scalar()
        )
        next_version = (max_version or 0) + 1

        now = datetime.now(timezone.utc)

        # Deactivate the currently active version (if any).
        db.query(IataFir).filter(
            IataFir.icao_code == icao_code,
            IataFir.is_active == True,  # noqa: E712 — SQLAlchemy filter
        ).update(
            {
                IataFir.is_active: False,
                IataFir.deactivation_date: now,
            },
            synchronize_session="fetch",
        )

        # Insert the new version as active.
        new_fir = IataFir(
            icao_code=icao_code,
            fir_name=fir_data["fir_name"],
            country_code=fir_data["country_code"],
            geojson_geometry=fir_data["geojson_geometry"],
            version_number=next_version,
            is_active=True,
            effective_date=fir_data.get("effective_date"),
            activation_date=now,
            created_at=now,
            created_by=fir_data.get("created_by", "freshness_checker"),
            bbox_min_lon=fir_data.get("bbox_min_lon"),
            bbox_min_lat=fir_data.get("bbox_min_lat"),
            bbox_max_lon=fir_data.get("bbox_max_lon"),
            bbox_max_lat=fir_data.get("bbox_max_lat"),
            avoid_status=fir_data.get("avoid_status", False),
        )
        db.add(new_fir)
        db.flush()

        logger.info(
            "Imported FIR version %d for %s",
            next_version,
            icao_code,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _query_unit_rates(db: Session) -> dict[str, Any]:
        """Query the latest unit rate month from eurocontrol_unit_rates.

        Compares the latest ``date_to`` against the current month to
        determine staleness.  Data is considered stale when the latest
        local period ends before the current calendar month.

        Validates Requirements: 15.1, 15.2
        """
        result: dict[str, Any] = {
            "latest_local_month": None,
            "is_stale": True,
            "source": "EUROCONTROL",
        }

        try:
            row = db.execute(
                text(
                    "SELECT MAX(date_to) AS latest_date_to "
                    "FROM eurocontrol_unit_rates"
                )
            ).fetchone()

            if row and row.latest_date_to:
                latest = row.latest_date_to
                # Format as YYYY-MM
                if hasattr(latest, "strftime"):
                    result["latest_local_month"] = latest.strftime("%Y-%m")
                else:
                    result["latest_local_month"] = str(latest)[:7]

                # Stale if the latest period ends before the current month
                today = date.today()
                current_month_start = today.replace(day=1)
                if hasattr(latest, "date"):
                    latest_date = latest.date()
                elif isinstance(latest, date):
                    latest_date = latest
                else:
                    latest_date = None

                if latest_date is not None:
                    result["is_stale"] = latest_date < current_month_start

        except Exception:
            logger.debug(
                "Could not query eurocontrol_unit_rates freshness",
                exc_info=True,
            )

        return result

    @staticmethod
    def _query_fir_boundaries(db: Session) -> dict[str, Any]:
        """Query FIR boundary summary from iata_firs.

        Returns total count of active FIR boundaries and the most
        recent ``created_at`` timestamp.
        """
        result: dict[str, Any] = {
            "total_count": 0,
            "latest_update": None,
        }

        try:
            row = db.query(
                func.count(IataFir.id).label("total"),
                func.max(IataFir.created_at).label("latest"),
            ).filter(
                IataFir.is_active == True,  # noqa: E712
            ).first()

            if row:
                result["total_count"] = row.total or 0
                if row.latest:
                    if hasattr(row.latest, "isoformat"):
                        result["latest_update"] = row.latest.isoformat()
                    else:
                        result["latest_update"] = str(row.latest)

        except Exception:
            logger.debug(
                "Could not query FIR boundary summary",
                exc_info=True,
            )

        return result
