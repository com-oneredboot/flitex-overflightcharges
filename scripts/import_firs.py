#!/usr/bin/env python3
"""
FIR Data Importer Script

Imports FIR (Flight Information Region) boundary data from an existing SQLite
database into the versioned PostgreSQL iata_firs table. Reads from the
fir_polygons table, uses CountryCodeMapper for country_code resolution,
and inserts with versioning columns (version_number=1, is_active=True,
created_by="system-import").

Usage:
    python scripts/import_firs.py --sqlite-path /path/to/iata_fir_complete.db

Requirements: 8.1, 8.2, 8.8, 8.9, 8.10, 8.11
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, List

import pycountry

from sqlalchemy.orm import Session

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SessionLocal, DATABASE_URL
from src.models.iata_fir import IataFir
from scripts.country_code_mapper import CountryCodeMapper


# Configure structured JSON logging
class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "service_name": "fir-importer",
            "message": record.getMessage(),
            "logger_name": record.name,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


# Setup logging
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logger = logging.getLogger(__name__)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments with sqlite_path attribute.
    """
    parser = argparse.ArgumentParser(
        description="Import FIR data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        required=True,
        help="Path to iata_fir_complete.db SQLite database",
    )
    return parser.parse_args()


def validate_sqlite_database(sqlite_path: str) -> None:
    """Validate that SQLite database exists and is accessible.

    Args:
        sqlite_path: Path to SQLite database file.

    Raises:
        SystemExit: If database is not accessible (exits with code 1).
    """
    db_file = Path(sqlite_path)

    if not db_file.exists():
        logger.error(f"SQLite database not found at path: {sqlite_path}")
        sys.exit(1)

    if not db_file.is_file():
        logger.error(f"Path is not a file: {sqlite_path}")
        sys.exit(1)

    try:
        conn = sqlite3.connect(sqlite_path)
        conn.close()
        logger.info(f"Successfully validated SQLite database: {sqlite_path}")
    except sqlite3.Error as e:
        logger.error(f"Cannot access SQLite database: {str(e)}")
        sys.exit(1)


def validate_fir_polygons_table(sqlite_path: str) -> None:
    """Validate that the fir_polygons table exists in the SQLite database.

    Args:
        sqlite_path: Path to SQLite database file.

    Raises:
        SystemExit: If fir_polygons table is missing (exits with code 1).
    """
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fir_polygons'"
        )
        if cursor.fetchone() is None:
            logger.error("Table 'fir_polygons' not found in SQLite database")
            conn.close()
            sys.exit(1)
        conn.close()
    except sqlite3.Error as e:
        logger.error(f"Failed to check for fir_polygons table: {str(e)}")
        sys.exit(1)


def read_fir_records_from_sqlite(sqlite_path: str) -> List[Dict[str, Any]]:
    """Read all FIR records from the fir_polygons table in SQLite.

    Args:
        sqlite_path: Path to SQLite database file.

    Returns:
        List of FIR records as dictionaries.

    Raises:
        SystemExit: If reading fails (exits with code 1).
    """
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM fir_polygons")
        rows = cursor.fetchall()

        records = [dict(row) for row in rows]
        conn.close()

        logger.info(f"Read {len(records)} FIR records from fir_polygons table")
        return records

    except sqlite3.Error as e:
        logger.error(f"Failed to read from SQLite database: {str(e)}")
        sys.exit(1)


def transform_record(
    record: Dict[str, Any], mapper: CountryCodeMapper
) -> Dict[str, Any]:
    """Transform a SQLite fir_polygons record to the versioned PostgreSQL schema.

    Uses CountryCodeMapper to resolve country_code from country_name since
    the SQLite source has empty country_code for all rows. Generates a
    descriptive fir_name in the format "{Country Name} FIR ({ICAO Code})"
    using pycountry to resolve the country name from country_code.

    Args:
        record: SQLite FIR record dictionary from fir_polygons table.
        mapper: CountryCodeMapper instance for country_code resolution.

    Returns:
        Transformed record matching the versioned IataFir model schema.
    """
    # Parse GeoJSON geometry if it's a string
    geojson_geometry = record.get("geojson_geometry")
    if isinstance(geojson_geometry, str):
        geojson_geometry = json.loads(geojson_geometry)

    # Resolve country_code from country_name using mapper
    country_name = record.get("country_name", "")
    country_code = mapper.map(country_name)

    # Generate descriptive fir_name: "{Country Name} FIR ({ICAO Code})"
    icao_code = record.get("icao_code", "")
    country = pycountry.countries.get(alpha_2=country_code)
    resolved_name = country.name if country else country_code
    fir_name = f"{resolved_name} FIR ({icao_code})"

    # Convert numeric fields to Decimal for precision
    bbox_min_lon = record.get("bbox_min_lon")
    bbox_min_lat = record.get("bbox_min_lat")
    bbox_max_lon = record.get("bbox_max_lon")
    bbox_max_lat = record.get("bbox_max_lat")

    now = datetime.now(timezone.utc)

    return {
        "icao_code": icao_code,
        "fir_name": fir_name,
        "country_code": country_code,
        "geojson_geometry": geojson_geometry,
        "bbox_min_lon": Decimal(str(bbox_min_lon)) if bbox_min_lon is not None else None,
        "bbox_min_lat": Decimal(str(bbox_min_lat)) if bbox_min_lat is not None else None,
        "bbox_max_lon": Decimal(str(bbox_max_lon)) if bbox_max_lon is not None else None,
        "bbox_max_lat": Decimal(str(bbox_max_lat)) if bbox_max_lat is not None else None,
        "avoid_status": bool(record.get("avoid_status", False)),
        # Versioning columns
        "version_number": 1,
        "is_active": True,
        "created_by": "system-import",
        "activation_date": now,
    }


def import_fir_data(sqlite_path: str) -> None:
    """Main import function that orchestrates the FIR data import process.

    Reads from fir_polygons table, deduplicates by icao_code (keeps first
    occurrence), resolves country_code via CountryCodeMapper, and inserts
    versioned records into PostgreSQL.

    Args:
        sqlite_path: Path to SQLite database file.

    Raises:
        SystemExit: On critical errors (exits with code 1).
    """
    # Validate PostgreSQL connection
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)

    if not SessionLocal:
        logger.error("Database session factory is not initialized")
        sys.exit(1)

    # Validate SQLite database and table
    validate_sqlite_database(sqlite_path)
    validate_fir_polygons_table(sqlite_path)

    # Read records from SQLite
    sqlite_records = read_fir_records_from_sqlite(sqlite_path)

    if not sqlite_records:
        logger.warning("No FIR records found in fir_polygons table")
        sys.exit(0)

    # Initialize mapper
    mapper = CountryCodeMapper()

    # Deduplicate by icao_code, keeping first occurrence
    seen_icao_codes: set = set()
    unique_records: List[Dict[str, Any]] = []
    skipped_duplicates = 0

    for record in sqlite_records:
        icao_code = record.get("icao_code")
        if icao_code in seen_icao_codes:
            skipped_duplicates += 1
            logger.info(f"Skipping duplicate icao_code: {icao_code}")
            continue
        seen_icao_codes.add(icao_code)
        unique_records.append(record)

    # Import records to PostgreSQL
    imported_count = 0
    error_count = 0
    unmapped_country_names: List[str] = []

    db: Session = SessionLocal()
    try:
        for record in unique_records:
            try:
                transformed = transform_record(record, mapper)

                # Track unmapped country names (those that fell back to "XX")
                if transformed["country_code"] == "XX":
                    unmapped_country_names.append(record.get("country_name", ""))

                fir = IataFir(**transformed)
                db.add(fir)
                imported_count += 1

            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import FIR {record.get('icao_code', 'UNKNOWN')}: {str(e)}"
                )

        # Commit all changes
        db.commit()

        # Log summary
        logger.info(
            f"FIR import completed: {imported_count} imported, "
            f"{skipped_duplicates} skipped duplicates, "
            f"{error_count} errors"
        )

        if unmapped_country_names:
            logger.warning(
                f"Unmapped country names ({len(unmapped_country_names)}): "
                f"{unmapped_country_names}"
            )

    except Exception as e:
        db.rollback()
        logger.error(f"Transaction commit failed: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    """Main entry point for the FIR importer script."""
    args = parse_arguments()

    logger.info("Starting FIR data import")
    logger.info(f"SQLite database path: {args.sqlite_path}")

    try:
        import_fir_data(args.sqlite_path)
        logger.info("FIR import completed successfully")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"FIR import failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
