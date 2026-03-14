"""Unit tests for the rewritten FIR importer script.

Tests the versioned import pipeline that reads from fir_polygons table,
uses CountryCodeMapper for country_code resolution, deduplicates by icao_code,
and inserts with versioning columns.

Requirements: 8.1, 8.2, 8.8, 8.9, 8.10, 8.11
"""

import json
import pytest
import sqlite3
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

# Import the script functions
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from import_firs import (
    parse_arguments,
    validate_sqlite_database,
    validate_fir_polygons_table,
    read_fir_records_from_sqlite,
    transform_record,
    import_fir_data,
)

from src.models.iata_fir import IataFir
from scripts.country_code_mapper import CountryCodeMapper


SAMPLE_GEOJSON = {
    "type": "Polygon",
    "coordinates": [
        [[-74.0, 40.0], [-73.0, 40.0], [-73.0, 41.0], [-74.0, 41.0], [-74.0, 40.0]]
    ],
}


@pytest.fixture
def mapper():
    """Create a CountryCodeMapper instance."""
    return CountryCodeMapper()


@pytest.fixture
def temp_sqlite_db():
    """Create a temporary SQLite database with fir_polygons table and sample data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE fir_polygons (
            icao_code TEXT,
            fir_name TEXT NOT NULL,
            country_name TEXT NOT NULL,
            country_code TEXT,
            geojson_geometry TEXT NOT NULL,
            bbox_min_lon REAL,
            bbox_min_lat REAL,
            bbox_max_lon REAL,
            bbox_max_lat REAL
        )
    """)

    geojson_str = json.dumps(SAMPLE_GEOJSON)

    cursor.execute(
        "INSERT INTO fir_polygons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("KJFK", "New York FIR", "United States", "", geojson_str, -74.0, 40.0, -73.0, 41.0),
    )
    cursor.execute(
        "INSERT INTO fir_polygons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("EGLL", "London FIR", "United Kingdom", "", geojson_str, -1.0, 51.0, 0.0, 52.0),
    )

    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink()


@pytest.fixture
def temp_sqlite_db_with_duplicates():
    """Create a SQLite database with duplicate icao_codes in fir_polygons."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE fir_polygons (
            icao_code TEXT,
            fir_name TEXT NOT NULL,
            country_name TEXT NOT NULL,
            country_code TEXT,
            geojson_geometry TEXT NOT NULL,
            bbox_min_lon REAL,
            bbox_min_lat REAL,
            bbox_max_lon REAL,
            bbox_max_lat REAL
        )
    """)

    geojson_str = json.dumps(SAMPLE_GEOJSON)

    cursor.execute(
        "INSERT INTO fir_polygons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("KJFK", "New York FIR", "United States", "", geojson_str, -74.0, 40.0, -73.0, 41.0),
    )
    cursor.execute(
        "INSERT INTO fir_polygons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("KJFK", "New York FIR Duplicate", "United States", "", geojson_str, -74.0, 40.0, -73.0, 41.0),
    )
    cursor.execute(
        "INSERT INTO fir_polygons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("EGLL", "London FIR", "United Kingdom", "", geojson_str, -1.0, 51.0, 0.0, 52.0),
    )

    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink()


@pytest.fixture
def temp_sqlite_db_no_table():
    """Create a SQLite database without the fir_polygons table."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE other_table (id INTEGER)")
    conn.commit()
    conn.close()

    yield db_path

    Path(db_path).unlink()


@pytest.fixture
def sample_fir_polygons_record():
    """A sample record as returned from the fir_polygons table."""
    return {
        "icao_code": "KJFK",
        "fir_name": "New York FIR",
        "country_name": "United States",
        "country_code": "",
        "geojson_geometry": json.dumps(SAMPLE_GEOJSON),
        "bbox_min_lon": -74.0,
        "bbox_min_lat": 40.0,
        "bbox_max_lon": -73.0,
        "bbox_max_lat": 41.0,
    }


class TestValidateSqliteDatabase:
    """Tests for validate_sqlite_database function."""

    def test_validate_existing_database(self, temp_sqlite_db):
        """Test validation of existing SQLite database."""
        validate_sqlite_database(temp_sqlite_db)

    def test_validate_nonexistent_database(self):
        """Test validation fails for non-existent database."""
        with pytest.raises(SystemExit) as exc_info:
            validate_sqlite_database("/nonexistent/path/database.db")
        assert exc_info.value.code == 1

    def test_validate_directory_instead_of_file(self, tmp_path):
        """Test validation fails when path is a directory."""
        with pytest.raises(SystemExit) as exc_info:
            validate_sqlite_database(str(tmp_path))
        assert exc_info.value.code == 1


class TestValidateFirPolygonsTable:
    """Tests for validate_fir_polygons_table function."""

    def test_table_exists(self, temp_sqlite_db):
        """Test validation passes when fir_polygons table exists."""
        validate_fir_polygons_table(temp_sqlite_db)

    def test_table_missing(self, temp_sqlite_db_no_table):
        """Test validation fails when fir_polygons table is missing."""
        with pytest.raises(SystemExit) as exc_info:
            validate_fir_polygons_table(temp_sqlite_db_no_table)
        assert exc_info.value.code == 1


class TestReadFirRecordsFromSqlite:
    """Tests for read_fir_records_from_sqlite function."""

    def test_read_records_success(self, temp_sqlite_db):
        """Test reading FIR records from fir_polygons table."""
        records = read_fir_records_from_sqlite(temp_sqlite_db)

        assert isinstance(records, list)
        assert len(records) == 2
        assert records[0]["icao_code"] == "KJFK"
        assert records[1]["icao_code"] == "EGLL"
        # country_code should be empty in source
        assert records[0]["country_code"] == ""

    def test_read_records_from_invalid_database(self):
        """Test reading from invalid database raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            read_fir_records_from_sqlite("/nonexistent/database.db")
        assert exc_info.value.code == 1


class TestTransformRecord:
    """Tests for transform_record function."""

    def test_transform_with_string_geojson(self, sample_fir_polygons_record, mapper):
        """Test transformation resolves country_code, generates descriptive fir_name, and parses GeoJSON string."""
        transformed = transform_record(sample_fir_polygons_record, mapper)

        assert transformed["icao_code"] == "KJFK"
        assert transformed["fir_name"] == "United States FIR (KJFK)"
        assert transformed["country_code"] == "US"
        assert "country_name" not in transformed
        assert isinstance(transformed["geojson_geometry"], dict)
        assert transformed["geojson_geometry"]["type"] == "Polygon"
        assert isinstance(transformed["bbox_min_lon"], Decimal)
        assert transformed["bbox_min_lon"] == Decimal("-74.0")

    def test_transform_sets_versioning_columns(self, sample_fir_polygons_record, mapper):
        """Test transformation sets version_number, is_active, created_by, activation_date."""
        transformed = transform_record(sample_fir_polygons_record, mapper)

        assert transformed["version_number"] == 1
        assert transformed["is_active"] is True
        assert transformed["created_by"] == "system-import"
        assert isinstance(transformed["activation_date"], datetime)

    def test_transform_with_dict_geojson(self, mapper):
        """Test transformation when geojson_geometry is already a dict."""
        record = {
            "icao_code": "TEST",
            "fir_name": "Test FIR",
            "country_name": "Germany",
            "country_code": "",
            "geojson_geometry": SAMPLE_GEOJSON,
            "bbox_min_lon": 10.5,
            "bbox_min_lat": 20.5,
            "bbox_max_lon": 30.5,
            "bbox_max_lat": 40.5,
        }

        transformed = transform_record(record, mapper)

        assert isinstance(transformed["geojson_geometry"], dict)
        assert transformed["country_code"] == "DE"
        assert transformed["fir_name"] == "Germany FIR (TEST)"
        assert "country_name" not in transformed

    def test_transform_with_null_bbox(self, mapper):
        """Test transformation with null bounding box values."""
        record = {
            "icao_code": "TEST",
            "fir_name": "Test FIR",
            "country_name": "France",
            "country_code": "",
            "geojson_geometry": SAMPLE_GEOJSON,
            "bbox_min_lon": None,
            "bbox_min_lat": None,
            "bbox_max_lon": None,
            "bbox_max_lat": None,
        }

        transformed = transform_record(record, mapper)

        assert transformed["bbox_min_lon"] is None
        assert transformed["bbox_min_lat"] is None
        assert transformed["bbox_max_lon"] is None
        assert transformed["bbox_max_lat"] is None
        assert "country_name" not in transformed

    def test_transform_unmapped_country_falls_back_to_xx(self, mapper):
        """Test that unmappable country_name falls back to 'XX' and uses it in descriptive fir_name."""
        record = {
            "icao_code": "ZZZZ",
            "fir_name": "Unknown FIR",
            "country_name": "Nonexistent Country XYZ123",
            "country_code": "",
            "geojson_geometry": SAMPLE_GEOJSON,
            "bbox_min_lon": None,
            "bbox_min_lat": None,
            "bbox_max_lon": None,
            "bbox_max_lat": None,
        }

        transformed = transform_record(record, mapper)

        assert transformed["country_code"] == "XX"
        assert transformed["fir_name"] == "XX FIR (ZZZZ)"
        assert "country_name" not in transformed

    def test_transform_manual_override_country(self, mapper):
        """Test that manual override country names are resolved correctly with descriptive fir_name."""
        record = {
            "icao_code": "WBFC",
            "fir_name": "Kota Kinabalu FIR",
            "country_name": "Brunei / Malaysia",
            "country_code": "",
            "geojson_geometry": SAMPLE_GEOJSON,
            "bbox_min_lon": None,
            "bbox_min_lat": None,
            "bbox_max_lon": None,
            "bbox_max_lat": None,
        }

        transformed = transform_record(record, mapper)

        assert transformed["country_code"] == "BN"
        assert transformed["fir_name"] == "Brunei Darussalam FIR (WBFC)"
        assert "country_name" not in transformed


class TestDeduplication:
    """Tests for icao_code deduplication in the import pipeline."""

    def test_read_duplicates_from_sqlite(self, temp_sqlite_db_with_duplicates):
        """Test that SQLite source can contain duplicate icao_codes."""
        records = read_fir_records_from_sqlite(temp_sqlite_db_with_duplicates)
        assert len(records) == 3  # 2 KJFK + 1 EGLL

    def test_deduplication_keeps_first_occurrence(self, temp_sqlite_db_with_duplicates, mapper):
        """Test that deduplication keeps first occurrence per icao_code."""
        records = read_fir_records_from_sqlite(temp_sqlite_db_with_duplicates)

        seen_icao_codes = set()
        unique_records = []
        skipped = 0

        for record in records:
            icao_code = record.get("icao_code")
            if icao_code in seen_icao_codes:
                skipped += 1
                continue
            seen_icao_codes.add(icao_code)
            unique_records.append(record)

        assert len(unique_records) == 2
        assert skipped == 1
        # First KJFK record should be kept
        assert unique_records[0]["fir_name"] == "New York FIR"


class TestParseArguments:
    """Tests for parse_arguments function."""

    def test_parse_arguments_with_sqlite_path(self):
        """Test parsing command line arguments with sqlite-path."""
        with patch("sys.argv", ["import_firs.py", "--sqlite-path", "/path/to/db.db"]):
            args = parse_arguments()
            assert args.sqlite_path == "/path/to/db.db"

    def test_parse_arguments_missing_required(self):
        """Test parsing fails when required argument is missing."""
        with patch("sys.argv", ["import_firs.py"]):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestIntegration:
    """Integration tests for the import process."""

    def test_full_transform_pipeline(self, temp_sqlite_db, mapper):
        """Test reading from fir_polygons, transforming with mapper, and verifying output."""
        records = read_fir_records_from_sqlite(temp_sqlite_db)
        assert len(records) == 2

        transformed_records = [transform_record(r, mapper) for r in records]

        # Verify versioning columns on all records
        for t in transformed_records:
            assert t["version_number"] == 1
            assert t["is_active"] is True
            assert t["created_by"] == "system-import"
            assert isinstance(t["activation_date"], datetime)
            assert "country_name" not in t

        # Verify country_code resolution and descriptive fir_name
        assert transformed_records[0]["country_code"] == "US"
        assert transformed_records[0]["fir_name"] == "United States FIR (KJFK)"
        assert transformed_records[1]["country_code"] == "GB"
        assert transformed_records[1]["fir_name"] == "United Kingdom FIR (EGLL)"

    def test_deduplication_in_pipeline(self, temp_sqlite_db_with_duplicates, mapper):
        """Test full pipeline with deduplication."""
        records = read_fir_records_from_sqlite(temp_sqlite_db_with_duplicates)

        seen = set()
        unique = []
        skipped = 0
        for r in records:
            if r["icao_code"] in seen:
                skipped += 1
                continue
            seen.add(r["icao_code"])
            unique.append(r)

        transformed = [transform_record(r, mapper) for r in unique]

        assert len(transformed) == 2
        assert skipped == 1
        icao_codes = [t["icao_code"] for t in transformed]
        assert "KJFK" in icao_codes
        assert "EGLL" in icao_codes
