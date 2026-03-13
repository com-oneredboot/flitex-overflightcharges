#!/usr/bin/env python3
"""
FIR Data Importer Script

Imports FIR (Flight Information Region) boundary data from an existing SQLite
database into the PostgreSQL database. Supports both initial imports and updates
to existing records using upsert behavior.

Usage:
    python scripts/import_firs.py --sqlite-path /path/to/iata-fir-system.db

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SessionLocal, DATABASE_URL
from src.models.iata_fir import IataFir


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
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments with sqlite_path attribute
    """
    parser = argparse.ArgumentParser(
        description="Import FIR data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        required=True,
        help="Path to iata-fir-system.db SQLite database"
    )
    return parser.parse_args()


def validate_sqlite_database(sqlite_path: str) -> None:
    """
    Validate that SQLite database exists and is accessible.
    
    Args:
        sqlite_path: Path to SQLite database file
    
    Raises:
        SystemExit: If database is not accessible (exits with code 1)
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


def read_fir_records_from_sqlite(sqlite_path: str) -> list[Dict[str, Any]]:
    """
    Read all FIR records from SQLite database.
    
    Args:
        sqlite_path: Path to SQLite database file
    
    Returns:
        List of FIR records as dictionaries
    
    Raises:
        SystemExit: If reading fails (exits with code 1)
    """
    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query all FIR records
        cursor.execute("SELECT * FROM firs")
        rows = cursor.fetchall()
        
        records = [dict(row) for row in rows]
        conn.close()
        
        logger.info(f"Read {len(records)} FIR records from SQLite database")
        return records
        
    except sqlite3.Error as e:
        logger.error(f"Failed to read from SQLite database: {str(e)}")
        sys.exit(1)


def transform_record_to_postgres_schema(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform SQLite record to PostgreSQL schema format.
    
    Args:
        record: SQLite FIR record dictionary
    
    Returns:
        Transformed record matching PostgreSQL IataFir model schema
    """
    # Parse GeoJSON geometry if it's a string
    geojson_geometry = record.get("geojson_geometry")
    if isinstance(geojson_geometry, str):
        geojson_geometry = json.loads(geojson_geometry)
    
    # Convert numeric fields to Decimal for precision
    bbox_min_lon = record.get("bbox_min_lon")
    bbox_min_lat = record.get("bbox_min_lat")
    bbox_max_lon = record.get("bbox_max_lon")
    bbox_max_lat = record.get("bbox_max_lat")
    
    transformed = {
        "icao_code": record.get("icao_code"),
        "fir_name": record.get("fir_name"),
        "country_code": record.get("country_code"),
        "country_name": record.get("country_name"),
        "geojson_geometry": geojson_geometry,
        "bbox_min_lon": Decimal(str(bbox_min_lon)) if bbox_min_lon is not None else None,
        "bbox_min_lat": Decimal(str(bbox_min_lat)) if bbox_min_lat is not None else None,
        "bbox_max_lon": Decimal(str(bbox_max_lon)) if bbox_max_lon is not None else None,
        "bbox_max_lat": Decimal(str(bbox_max_lat)) if bbox_max_lat is not None else None,
        "avoid_status": bool(record.get("avoid_status", False)),
    }
    
    return transformed


def upsert_fir_record(session: Session, record: Dict[str, Any]) -> str:
    """
    Insert or update FIR record in PostgreSQL database.
    
    Uses INSERT ... ON CONFLICT UPDATE for upsert behavior.
    
    Args:
        session: SQLAlchemy database session
        record: Transformed FIR record dictionary
    
    Returns:
        "inserted" or "updated" to indicate operation performed
    """
    icao_code = record["icao_code"]
    
    # Check if record exists
    existing = session.query(IataFir).filter(IataFir.icao_code == icao_code).first()
    
    if existing:
        # Update existing record
        for key, value in record.items():
            if key != "icao_code":  # Don't update primary key
                setattr(existing, key, value)
        return "updated"
    else:
        # Insert new record
        new_fir = IataFir(**record)
        session.add(new_fir)
        return "inserted"


def import_fir_data(sqlite_path: str) -> None:
    """
    Main import function that orchestrates the FIR data import process.
    
    Args:
        sqlite_path: Path to SQLite database file
    
    Raises:
        SystemExit: On any error (exits with code 1)
    """
    # Validate PostgreSQL connection
    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    if not SessionLocal:
        logger.error("Database session factory is not initialized")
        sys.exit(1)
    
    # Validate SQLite database
    validate_sqlite_database(sqlite_path)
    
    # Read records from SQLite
    sqlite_records = read_fir_records_from_sqlite(sqlite_path)
    
    if not sqlite_records:
        logger.warning("No FIR records found in SQLite database")
        sys.exit(0)
    
    # Import records to PostgreSQL
    inserted_count = 0
    updated_count = 0
    error_count = 0
    
    db = SessionLocal()
    try:
        for record in sqlite_records:
            try:
                # Transform record
                transformed = transform_record_to_postgres_schema(record)
                
                # Upsert record
                operation = upsert_fir_record(db, transformed)
                
                if operation == "inserted":
                    inserted_count += 1
                else:
                    updated_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(
                    f"Failed to import FIR {record.get('icao_code', 'UNKNOWN')}: {str(e)}"
                )
        
        # Commit all changes
        db.commit()
        
        # Log summary
        logger.info(
            f"FIR import completed: {inserted_count} inserted, "
            f"{updated_count} updated, {error_count} errors"
        )
        
        if error_count > 0:
            logger.warning(f"Import completed with {error_count} errors")
            sys.exit(1)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed: {str(e)}")
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
    except Exception as e:
        logger.error(f"FIR import failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
