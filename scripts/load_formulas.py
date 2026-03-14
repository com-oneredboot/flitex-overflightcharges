"""Load pre-converted Python formula files into the formulas database table."""

import os
import sys
import hashlib
import uuid
from datetime import date, datetime, timezone

# Country name to ISO 3166-1 alpha-2 mapping
COUNTRY_CODE_MAP = {
    "Afghanistan": "AF",
    "Algeria": "DZ",
    "Angola": "AO",
    "Argentina": "AR",
    "Aruba": "AW",
    "Ashgabat": None,  # Ashgabat FIR - treat as regional (Turkmenistan TM used by Turkmenistan.py)
    "Australia": "AU",
    "Azerbaijan": "AZ",
    "Bahamas": "BS",
    "Bahrain": "BH",
    "Belize": "BZ",
    "Bermuda": "BM",
    "Botswana": "BW",
    "Brazil": "BR",
    "Canada": "CA",
    "CapeVerde": "CV",
    "Chad": "TD",
    "Chile": "CL",
    "China": "CN",
    "Colombia": "CO",
    "CongoDRC": "CD",
    "CostaRica": "CR",
    "Cuba": "CU",
    "DominicanRepublic": "DO",
    "Ecuador": "EC",
    "Egypt": "EG",
    "ElSalvador": "SV",
    "Ethiopia": "ET",
    "EuroControl": None,  # Regional, not a country
    "Fiji": "FJ",
    "FrenchGuiana": "GF",
    "FrenchPolynesia": "PF",
    "Ghana": "GH",
    "Greenland": "GL",
    "Guyana": "GY",
    "Haiti": "HT",
    "Honduras": "HN",
    "HongKong": "HK",
    "Iceland": "IS",
    "India": "IN",
    "Indonesia": "ID",
    "Iran": "IR",
    "Iraq": "IQ",
    "Israel": "IL",
    "Jamaica": "JM",
    "Japan": "JP",
    "Jordan": "JO",
    "Kazakhstan": "KZ",
    "Kuwait": "KW",
    "Kyrgyzstan": "KG",
    "Laos": "LA",
    "Liberia": "LR",
    "Libya": "LY",
    "Madagascar": "MG",
    "Malawi": "MW",
    "Malaysia": "MY",
    "Maldives": "MV",
    "Mauritius": "MU",
    "Mexico": "MX",
    "Mongolia": "MN",
    "Morocco": "MA",
    "Mozambique": "MZ",
    "Myanmar": "MM",
    "Namibia": "NA",
    "Nauru": "NR",
    "Nepal": "NP",
    "NetherlandsAntilles": "AN",
    "NewZealand": "NZ",
    "Niger": "NE",
    "NorthKorea": "KP",
    "Oceanic": None,  # Regional, not a country
    "Oman": "OM",
    "Pakistan": "PK",
    "Panama": "PA",
    "PapuaNewGuinea": "PG",
    "Peru": "PE",
    "Philippines": "PH",
    "Portugal": "PT",
    "Russia": "RU",
    "SaudiArabia": "SA",
    "Senegal": "SN",
    "Seychelles": "SC",
    "Singapore": "SG",
    "SolomonIslands": "SB",
    "Somalia": "SO",
    "SouthAfrica": "ZA",
    "SouthKorea": "KR",
    "Spain": "ES",
    "SriLanka": "LK",
    "Sudan": "SD",
    "Suriname": "SR",
    "Syria": "SY",
    "Taiwan": "TW",
    "Tajikistan": "TJ",
    "Thailand": "TH",
    "TrinidadAndTobago": "TT",
    "Tunisia": "TN",
    "Turkmenistan": "TM",
    "TurksandCaicos": "TC",
    "UK": "GB",
    "UnitedArabEmirates": "AE",
    "UnitedStates": "US",
    "Uzbekistan": "UZ",
    "Venezuela": "VE",
    "Vietnam": "VN",
    "Zambia": "ZM",
}

# Currency extraction from docstrings (fallback: USD)
def extract_currency(formula_text):
    """Try to extract currency from formula docstring or code."""
    import re
    # Look for currency in return dict
    match = re.search(r'"currency":\s*"([A-Z]{3})"', formula_text)
    if match:
        return match.group(1)
    # Look for Currency: XXX in docstring
    match = re.search(r'Currency:\s*([A-Z]{3})', formula_text)
    if match:
        return match.group(1)
    return "USD"


def make_description(name, country_code):
    """Create a human-readable description."""
    # Add spaces before capitals: EuroControl -> Euro Control
    import re
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', name)
    if country_code:
        return f"{spaced} ({country_code})"
    return spaced  # Regional formulas


def load_formulas():
    """Load all formula .py files into the database."""
    import psycopg2

    formulas_dir = os.path.join(os.path.dirname(__file__), "..", "formulas")
    
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="flitex_united_demo",
        user="route_user",
        password="BTUp4ronhUanJfcQSGxpaF6GFIkIRcB6",
    )
    conn.autocommit = False
    cur = conn.cursor()

    loaded = 0
    skipped = 0
    errors = []

    for filename in sorted(os.listdir(formulas_dir)):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue

        name = filename[:-3]  # Strip .py
        
        if name not in COUNTRY_CODE_MAP:
            errors.append(f"No country code mapping for: {name}")
            continue

        country_code = COUNTRY_CODE_MAP[name]
        filepath = os.path.join(formulas_dir, filename)

        with open(filepath, "r") as f:
            formula_logic = f.read()

        # Skip empty files
        if not formula_logic.strip():
            skipped += 1
            continue

        currency = extract_currency(formula_logic)
        description = make_description(name, country_code)
        formula_hash = hashlib.sha256(formula_logic.encode()).hexdigest()
        formula_code = f"{country_code or name}_v1"

        try:
            cur.execute(
                """
                INSERT INTO formulas (
                    id, country_code, description, formula_code,
                    formula_logic, effective_date, currency,
                    version_number, is_active, activation_date,
                    created_at, created_by, formula_hash
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s
                )
                """,
                (
                    str(uuid.uuid4()),
                    country_code,
                    description,
                    formula_code,
                    formula_logic,
                    date(2025, 1, 1),
                    currency,
                    1,
                    True,
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    "formula_loader",
                    formula_hash,
                ),
            )
            loaded += 1
            print(f"  ✓ {name} -> {country_code or 'REGIONAL'} ({currency})")
        except Exception as e:
            errors.append(f"{name}: {e}")
            conn.rollback()
            # Reconnect after rollback for next insert
            conn.autocommit = False

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---")
        for err in errors:
            print(f"  ✗ {err}")

    if loaded > 0:
        conn.commit()
        print(f"\n✓ Loaded {loaded} formulas, skipped {skipped}")
    else:
        print(f"\nNo formulas loaded. Skipped: {skipped}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    load_formulas()
