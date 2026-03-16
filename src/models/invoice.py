"""SQLAlchemy models for the invoices and fir_entries tables.

Read-only models used by the overflight-charges service to query
parsed invoice records for the Invoice Filter / Matching feature (Step 4).
The tables are owned/populated by the invoice parser pipeline.
"""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database import Base


class Invoice(Base):
    """Invoice records from the invoices table (read-only).

    Each record represents a parsed overflight charge invoice with
    vendor, date, amount, currency, and associated FIR charge entries.
    """

    __tablename__ = "invoices"

    invoice_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename = Column(String(255), nullable=True)
    vendor = Column(String(100), nullable=True)
    invoice_number = Column(String(100), nullable=True)
    invoice_date = Column(Date, nullable=True)
    total_amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), nullable=True)
    language = Column(String(10), nullable=True)
    pages = Column(Integer, nullable=True)
    processing_date = Column(DateTime, nullable=True)

    fir_entries = relationship("FIREntry", back_populates="invoice", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<Invoice(invoice_id={self.invoice_id}, "
            f"vendor='{self.vendor}', "
            f"invoice_number='{self.invoice_number}', "
            f"invoice_date={self.invoice_date})>"
        )


class FIREntry(Base):
    """FIR charge line items from the fir_entries table (read-only).

    Each record represents a single FIR charge extracted from an invoice,
    linked to the parent invoice via invoice_id.
    """

    __tablename__ = "fir_entries"

    fir_entry_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    invoice_id = Column(
        UUID(as_uuid=True),
        ForeignKey("invoices.invoice_id"),
        nullable=False,
        index=True,
    )
    fir_code = Column(String(4), nullable=True, index=True)
    fir_name = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    amount = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(3), nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    extraction_method = Column(String(20), nullable=True)

    invoice = relationship("Invoice", back_populates="fir_entries")

    def __repr__(self) -> str:
        return (
            f"<FIREntry(fir_entry_id={self.fir_entry_id}, "
            f"invoice_id={self.invoice_id}, "
            f"fir_code='{self.fir_code}', "
            f"amount={self.amount})>"
        )
