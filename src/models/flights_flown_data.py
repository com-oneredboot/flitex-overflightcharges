"""SQLAlchemy model for the flights_flown_data table.

Read-only model used by the overflight-charges service to query
actual flown flight records for the Confirm Flown Data feature.
The table is owned/populated by the flights-flown-ingestion service.
"""

import uuid

from sqlalchemy import Column, Date, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from src.database import Base


class FlightsFlownData(Base):
    """Flight records from the flights_flown_data table (read-only).

    Each record represents a single actual flight with details including
    flight number, aircraft information, route, and cost data.
    """

    __tablename__ = "flights_flown_data"

    flight_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    flight_number = Column(String(20), nullable=False, index=True)
    registration = Column(String(20), nullable=True)
    date = Column(Date, nullable=False, index=True)
    origin = Column(String(4), nullable=False, index=True)
    destination = Column(String(4), nullable=False, index=True)
    aircraft_type = Column(String(20), nullable=True)
    distance = Column(Integer, nullable=True)
    cost = Column(Numeric(10, 2), nullable=True)
    user_number = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FlightsFlownData(flight_id={self.flight_id}, "
            f"flight_number='{self.flight_number}', date={self.date}, "
            f"route='{self.origin}/{self.destination}')>"
        )
