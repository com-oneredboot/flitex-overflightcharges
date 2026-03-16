"""Pydantic schemas for Invoice Search endpoint.

Defines request/response schemas for searching the invoices and fir_entries
tables and returning matched invoice records with FIR match scoring.

Validates Requirements: 1.1, 1.11, 10.1
"""

from pydantic import BaseModel, Field
from typing import Optional


class InvoiceSearchRequest(BaseModel):
    """Request schema for searching invoice data.

    All fields are optional. At least one search criterion must be provided.
    Fields aircraft_type, registration, origin, destination, and tenant_id
    are accepted for forward-compatibility but silently ignored until the
    corresponding database columns are added in a future migration.

    Validates Requirements: 1.1, 10.1
    """

    fir_codes: Optional[list[str]] = Field(
        None,
        description="ICAO FIR codes to match against fir_entries (e.g., ['CZQX', 'EGTT'])",
    )
    date_from: Optional[str] = Field(
        None,
        description="Start of date range in YYYY-MM-DD format",
    )
    date_to: Optional[str] = Field(
        None,
        description="End of date range in YYYY-MM-DD format",
    )
    vendor: Optional[str] = Field(
        None,
        description="Vendor name for substring matching (case-insensitive)",
    )
    currency: Optional[str] = Field(
        None,
        description="Currency code for exact matching (case-insensitive)",
    )
    min_amount: Optional[float] = Field(
        None,
        description="Minimum total_amount filter",
    )
    aircraft_type: Optional[str] = Field(
        None,
        description="Aircraft type designation (future: filter when column exists)",
    )
    registration: Optional[str] = Field(
        None,
        description="Aircraft registration number (future: filter when column exists)",
    )
    origin: Optional[str] = Field(
        None,
        description="Origin airport ICAO code (future: filter when column exists)",
    )
    destination: Optional[str] = Field(
        None,
        description="Destination airport ICAO code (future: filter when column exists)",
    )
    tenant_id: Optional[str] = Field(
        None,
        description="Tenant identifier for multi-tenant filtering (future: filter when column exists)",
    )


class FIREntryResponse(BaseModel):
    """Response schema for a single FIR charge line item extracted from an invoice.

    Validates Requirements: 1.11
    """

    fir_entry_id: str = Field(
        ...,
        description="Unique FIR entry identifier",
    )
    fir_code: str = Field(
        ...,
        description="ICAO FIR code",
    )
    fir_name: Optional[str] = Field(
        None,
        description="FIR region name",
    )
    country: Optional[str] = Field(
        None,
        description="Country associated with the FIR",
    )
    amount: Optional[float] = Field(
        None,
        description="Charge amount for this FIR entry",
    )
    currency: Optional[str] = Field(
        None,
        description="Currency code for the charge amount",
    )
    confidence: Optional[float] = Field(
        None,
        description="Extraction confidence score (0.0 to 1.0)",
    )
    extraction_method: Optional[str] = Field(
        None,
        description="Method used to extract this FIR entry",
    )


class InvoiceRecordResponse(BaseModel):
    """Response schema for a single matched invoice record.

    Includes all invoice metadata, associated FIR entries, and a computed
    FIR match score indicating how well the invoice matches the requested
    FIR codes.

    Validates Requirements: 1.11
    """

    invoice_id: str = Field(
        ...,
        description="Unique invoice identifier",
    )
    filename: str = Field(
        ...,
        description="Original invoice filename",
    )
    vendor: str = Field(
        ...,
        description="Invoice vendor name",
    )
    invoice_number: Optional[str] = Field(
        None,
        description="Invoice number",
    )
    invoice_date: Optional[str] = Field(
        None,
        description="Invoice date in YYYY-MM-DD format",
    )
    total_amount: Optional[float] = Field(
        None,
        description="Total invoice amount",
    )
    currency: Optional[str] = Field(
        None,
        description="Invoice currency code",
    )
    language: Optional[str] = Field(
        None,
        description="Invoice language",
    )
    pages: Optional[int] = Field(
        None,
        description="Number of pages in the invoice",
    )
    processing_date: Optional[str] = Field(
        None,
        description="Date the invoice was processed",
    )
    fir_entries: list[FIREntryResponse] = Field(
        ...,
        description="List of FIR charge line items extracted from this invoice",
    )
    fir_match_score: str = Field(
        ...,
        description="FIR match score: 'strong', 'moderate', or 'none'",
    )


class InvoiceSearchResponse(BaseModel):
    """Response schema for invoice search results.

    Contains the list of matched invoice records and total count.

    Validates Requirements: 1.1, 1.11
    """

    results: list[InvoiceRecordResponse] = Field(
        ...,
        description="List of matched invoice records with FIR match scoring",
    )
    total_count: int = Field(
        ...,
        description="Total number of matched records",
    )
