"""
Madagascar Overflight Charges Formula

Currency: EUR
Conversion: 1 EUR = 1.09 USD

Rates (with VSAT charge $9.60 USD):
- Under 14 tonnes:
  - Overflight: 211.69 EUR + VSAT
  - Domestic/International: 88.14 EUR + VSAT
- Over 14 tonnes:
  - Overflight: 105.84 EUR + VSAT
  - Domestic/International: 68.80 EUR + VSAT
"""


def calculate(distance, weight, context):
    """Calculate Madagascar overflight charges."""
    eur_to_usd = 1.09
    vsat_rate_usd = 9.60
    vsat_rate_eur = vsat_rate_usd / eur_to_usd

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    if origin_country != "Madagascar" and destination_country != "Madagascar":
        cost = (211.69 if weight <= 14 else 105.84) + vsat_rate_eur
    else:
        cost = (88.14 if weight <= 14 else 68.80) + vsat_rate_eur

    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
