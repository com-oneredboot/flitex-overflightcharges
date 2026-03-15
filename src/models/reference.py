"""SQLAlchemy models for reference schema tables.

Independent models for the overflight-charges backend, mapping to the
`reference` schema tables created by migration 04-create-reference-tables.sql.
These are separate from the deprecated API gateway models in
apps/api/models/reference.py.

Validates Requirements: 2.1, 2.3, 3.1
"""

from sqlalchemy import Column, Float, Integer, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB

from src.database import Base


class ReferenceAirport(Base):
    """Airport reference data from Little Navmap / Navigraph.

    Maps to reference.airports table. Used by the reference API for
    airport search/listing and by the route validator for waypoint
    resolution.

    Fields exposed via API: ident, iata, name, city, country
    Coordinates (laty, lonx) used for route waypoint resolution.
    """

    __tablename__ = "airports"
    __table_args__ = {"schema": "reference"}

    airport_id = Column(Integer, primary_key=True, autoincrement=True)
    ident = Column(String(10), nullable=False, unique=True, index=True)
    iata = Column(String(3), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    region = Column(String(10), nullable=True)
    laty = Column(Float, nullable=True)
    lonx = Column(Float, nullable=True)
    altitude = Column(Integer, nullable=True)
    mag_var = Column(Float, nullable=True)
    timezone = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceAirport(ident={self.ident}, name={self.name})>"


class ReferenceAircraft(Base):
    """Aircraft reference data from BADA.

    Maps to reference.aircrafts table. The `details` JSONB column
    contains aircraft specifications including `mass_max` (MTOW in kg)
    used for auto-populating the flight plan form.
    """

    __tablename__ = "aircrafts"
    __table_args__ = {"schema": "reference"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(20), nullable=False, unique=True, index=True)
    details = Column(JSONB, nullable=False, default={})
    created_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceAircraft(model={self.model})>"


class ReferenceNavWaypoint(Base):
    """Navigation waypoints (merged VOR/NDB/Waypoint from Navigraph).

    Maps to reference.nav_waypoints table. Used by the route validator
    to resolve waypoint identifiers to coordinates.
    """

    __tablename__ = "nav_waypoints"
    __table_args__ = {"schema": "reference"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ident = Column(String(10), nullable=False, index=True)
    region = Column(String(10), nullable=True)
    type = Column(String(20), nullable=True)
    laty = Column(Float, nullable=True)
    lonx = Column(Float, nullable=True)
    mag_var = Column(Float, nullable=True)
    altitude = Column(Integer, nullable=True)
    frequency = Column(Integer, nullable=True)
    range = Column(Integer, nullable=True)
    name = Column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceNavWaypoint(ident={self.ident}, type={self.type})>"


class ReferenceChargesWaypoint(Base):
    """Waypoints for overflight charges calculation.

    Maps to reference.charges_waypoints table. Used by the route
    validator as a fallback source for waypoint resolution.
    """

    __tablename__ = "charges_waypoints"
    __table_args__ = {"schema": "reference"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ident = Column(String(10), nullable=False, index=True)
    region = Column(String(10), nullable=True)
    arinc_type = Column(String(20), nullable=True)
    laty = Column(Float, nullable=True)
    lonx = Column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceChargesWaypoint(ident={self.ident})>"


class ReferenceChargesVOR(Base):
    """VOR stations for overflight charges calculation.

    Maps to reference.charges_vor table. Used by the route validator
    as a fallback source for waypoint resolution.
    """

    __tablename__ = "charges_vor"
    __table_args__ = {"schema": "reference"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ident = Column(String(10), nullable=False, index=True)
    region = Column(String(10), nullable=True)
    airport_ident = Column(String(10), nullable=True)
    laty = Column(Float, nullable=True)
    lonx = Column(Float, nullable=True)
    frequency = Column(Integer, nullable=True)
    range = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceChargesVOR(ident={self.ident})>"


class ReferenceChargesNDB(Base):
    """NDB stations for overflight charges calculation.

    Maps to reference.charges_ndb table. Used by the route validator
    as a fallback source for waypoint resolution.
    """

    __tablename__ = "charges_ndb"
    __table_args__ = {"schema": "reference"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    ident = Column(String(10), nullable=False, index=True)
    region = Column(String(10), nullable=True)
    name = Column(String(255), nullable=True)
    type = Column(String(20), nullable=True)
    laty = Column(Float, nullable=True)
    lonx = Column(Float, nullable=True)
    frequency = Column(Integer, nullable=True)
    range = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceChargesNDB(ident={self.ident})>"


class ReferenceFIRBoundary(Base):
    """Flight Information Region boundaries with PostGIS geometry.

    Maps to reference.fir_boundaries table. The geometry column stores
    PostGIS geometry data used for spatial analysis (FIR crossing
    identification during route validation).

    Note: The geometry column is mapped as a generic Column since this
    backend uses shapely (not geoalchemy2) for spatial operations.
    Spatial queries use ST_Contains/ST_Intersects via raw SQL or text().
    """

    __tablename__ = "fir_boundaries"
    __table_args__ = {"schema": "reference"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    icao_code = Column(String(10), unique=True, nullable=True)
    fir_name = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    continent = Column(String(50), nullable=True)
    geometry = Column("geometry", nullable=True)
    created_at = Column(TIMESTAMP, nullable=True)

    def __repr__(self) -> str:
        return f"<ReferenceFIRBoundary(icao_code={self.icao_code}, fir_name={self.fir_name})>"
