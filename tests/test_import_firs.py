"""Unit tests for FIR importer script."""

import json
import pytest
import sqlite3
import tempfile
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
    read_fir_records_from_sqlite,
    transform_record_to_postgres_schema,
    upsert_fir_record,
)

from src.models.iata_fir import IataFir


@pytest.fixture
def temp_sqlite_db():
    """Create a temporary SQLite database with sample FIR data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    # Create database and table
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE firs (
            icao_code TEXT PRIMARY KEY,
            fir_name TEXT NOT NULL,
            country_code TEXT NOT NULL,
            country_name TEXT NOT NULL,
            geojson_geometry TEXT NOT NULL,
            bbox_min_lon REAL,
            bbox_min_lat REAL,
            bbox_max_lon REAL,
            bbox_max_lat REAL,
            avoid_status INTEGER DEFAULT 0
        )
    """)
    
    # Insert sample data
    sample_geojson = json.dumps({
        "type": "Polygon",
        "coordinates": [[[-74.0, 40.0], [-73.0, 40.0], [-73.0, 41.0], [-74.0, 41.0], [-74.0, 40.0]]]
    })
    
    cursor.execute("""
        INSERT INTO firs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("KJFK", "New York FIR", "US", "United States", sample_geojson, -74.0, 40.0, -73.0, 41.0, 0))
    
    cursor.execute("""
        INSERT INTO firs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("EGLL", "London FIR", "GB", "United Kingdom", sample_geojson, -1.0, 51.0, 0.0, 52.0, 1))
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink()


@pytest.fixture
def sample_sqlite_record():
    """Create a sample SQLite FIR record."""
    return {
        "icao_code": "KJFK",
        "fir_name": "New York FIR",
        "country_code": "US",
        "country_name": "United States",
        "geojson_geometry": json.dumps({
            "type": "Polygon",
            "coordinates": [[[-74.0, 40.0], [-73.0, 40.0], [-73.0, 41.0], [-74.0, 41.0], [-74.0, 40.0]]]
        }),
        "bbox_min_lon": -74.0,
        "bbox_min_lat": 40.0,
        "bbox_max_lon": -73.0,
        "bbox_max_lat": 41.0,
        "avoid_status": 0
    }


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    return Mock(spec=Session)


class TestValidateSqliteDatabase:
    """Tests for validate_sqlite_database function."""
    
    def test_validate_existing_database(self, temp_sqlite_db):
        """Test validation of existing SQLite database."""
        # Should not raise exception
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


class TestReadFirRecordsFromSqlite:
    """Tests for read_fir_records_from_sqlite function."""
    
    def test_read_records_success(self, temp_sqlite_db):
        """Test reading FIR records from SQLite database."""
        records = read_fir_records_from_sqlite(temp_sqlite_db)
        
        assert isinstance(records, list)
        assert len(records) == 2
        assert records[0]["icao_code"] == "KJFK"
        assert records[1]["icao_code"] == "EGLL"
    
    def test_read_records_from_invalid_database(self):
        """Test reading from invalid database raises SystemExit."""
        with pytest.raises(SystemExit) as exc_info:
            read_fir_records_from_sqlite("/nonexistent/database.db")
        assert exc_info.value.code == 1


class TestTransformRecordToPostgresSchema:
    """Tests for transform_record_to_postgres_schema function."""
    
    def test_transform_record_with_string_geojson(self, sample_sqlite_record):
        """Test transformation of record with GeoJSON as string."""
        transformed = transform_record_to_postgres_schema(sample_sqlite_record)
        
        assert transformed["icao_code"] == "KJFK"
        assert transformed["fir_name"] == "New York FIR"
        assert transformed["country_code"] == "US"
        assert transformed["country_name"] == "United States"
        assert isinstance(transformed["geojson_geometry"], dict)
        assert transformed["geojson_geometry"]["type"] == "Polygon"
        assert isinstance(transformed["bbox_min_lon"], Decimal)
        assert transformed["bbox_min_lon"] == Decimal("-74.0")
        assert isinstance(transformed["bbox_min_lat"], Decimal)
        assert transformed["avoid_status"] is False
    
    def test_transform_record_with_dict_geojson(self):
        """Test transformation of record with GeoJSON as dict."""
        record = {
            "icao_code": "TEST",
            "fir_name": "Test FIR",
            "country_code": "TS",
            "country_name": "Test Country",
            "geojson_geometry": {"type": "Polygon", "coordinates": []},
            "bbox_min_lon": 10.5,
            "bbox_min_lat": 20.5,
            "bbox_max_lon": 30.5,
            "bbox_max_lat": 40.5,
            "avoid_status": 1
        }
        
        transformed = transform_record_to_postgres_schema(record)
        
        assert isinstance(transformed["geojson_geometry"], dict)
        assert transformed["avoid_status"] is True
    
    def test_transform_record_with_null_bbox(self):
        """Test transformation of record with null bounding box values."""
        record = {
            "icao_code": "TEST",
            "fir_name": "Test FIR",
            "country_code": "TS",
            "country_name": "Test Country",
            "geojson_geometry": {"type": "Polygon", "coordinates": []},
            "bbox_min_lon": None,
            "bbox_min_lat": None,
            "bbox_max_lon": None,
            "bbox_max_lat": None,
            "avoid_status": 0
        }
        
        transformed = transform_record_to_postgres_schema(record)
        
        assert transformed["bbox_min_lon"] is None
        assert transformed["bbox_min_lat"] is None
        assert transformed["bbox_max_lon"] is None
        assert transformed["bbox_max_lat"] is None


class TestUpsertFirRecord:
    """Tests for upsert_fir_record function."""
    
    def test_insert_new_record(self, mock_session):
        """Test inserting a new FIR record."""
        record = {
            "icao_code": "KJFK",
            "fir_name": "New York FIR",
            "country_code": "US",
            "country_name": "United States",
            "geojson_geometry": {"type": "Polygon", "coordinates": []},
            "bbox_min_lon": Decimal("-74.0"),
            "bbox_min_lat": Decimal("40.0"),
            "bbox_max_lon": Decimal("-73.0"),
            "bbox_max_lat": Decimal("41.0"),
            "avoid_status": False
        }
        
        # Mock query to return None (record doesn't exist)
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        result = upsert_fir_record(mock_session, record)
        
        assert result == "inserted"
        mock_session.add.assert_called_once()
    
    def test_update_existing_record(self, mock_session):
        """Test updating an existing FIR record."""
        record = {
            "icao_code": "KJFK",
            "fir_name": "Updated New York FIR",
            "country_code": "US",
            "country_name": "United States",
            "geojson_geometry": {"type": "Polygon", "coordinates": []},
            "bbox_min_lon": Decimal("-74.0"),
            "bbox_min_lat": Decimal("40.0"),
            "bbox_max_lon": Decimal("-73.0"),
            "bbox_max_lat": Decimal("41.0"),
            "avoid_status": True
        }
        
        # Create existing FIR
        existing_fir = IataFir(
            icao_code="KJFK",
            fir_name="Old New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={"type": "Polygon", "coordinates": []},
            avoid_status=False
        )
        
        # Mock query to return existing record
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = existing_fir
        
        result = upsert_fir_record(mock_session, record)
        
        assert result == "updated"
        assert existing_fir.fir_name == "Updated New York FIR"
        assert existing_fir.avoid_status is True
        mock_session.add.assert_not_called()


class TestParseArguments:
    """Tests for parse_arguments function."""
    
    def test_parse_arguments_with_sqlite_path(self):
        """Test parsing command line arguments with sqlite-path."""
        with patch('sys.argv', ['import_firs.py', '--sqlite-path', '/path/to/db.db']):
            args = parse_arguments()
            assert args.sqlite_path == '/path/to/db.db'
    
    def test_parse_arguments_missing_required(self):
        """Test parsing fails when required argument is missing."""
        with patch('sys.argv', ['import_firs.py']):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestIntegration:
    """Integration tests for the import process."""
    
    def test_full_import_process(self, temp_sqlite_db, mock_session):
        """Test the full import process from SQLite to PostgreSQL."""
        # Read records from SQLite
        records = read_fir_records_from_sqlite(temp_sqlite_db)
        assert len(records) == 2
        
        # Transform and upsert each record
        inserted_count = 0
        updated_count = 0
        
        # Mock query to return None (all records are new)
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        for record in records:
            transformed = transform_record_to_postgres_schema(record)
            operation = upsert_fir_record(mock_session, transformed)
            
            if operation == "inserted":
                inserted_count += 1
            else:
                updated_count += 1
        
        assert inserted_count == 2
        assert updated_count == 0
        assert mock_session.add.call_count == 2
    
    def test_import_with_existing_records(self, temp_sqlite_db, mock_session):
        """Test import process when some records already exist."""
        records = read_fir_records_from_sqlite(temp_sqlite_db)
        
        # Create existing FIR for first record
        existing_fir = IataFir(
            icao_code="KJFK",
            fir_name="Old New York FIR",
            country_code="US",
            country_name="United States",
            geojson_geometry={"type": "Polygon", "coordinates": []},
            avoid_status=False
        )
        
        # Mock query to return existing for first, None for second
        mock_query = Mock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [existing_fir, None]
        
        inserted_count = 0
        updated_count = 0
        
        for record in records:
            transformed = transform_record_to_postgres_schema(record)
            operation = upsert_fir_record(mock_session, transformed)
            
            if operation == "inserted":
                inserted_count += 1
            else:
                updated_count += 1
        
        assert inserted_count == 1
        assert updated_count == 1
        assert mock_session.add.call_count == 1
