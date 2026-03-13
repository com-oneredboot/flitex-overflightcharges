"""
Chad Overflight Charges Formula

Currency: EUR
Conversion: 1 EUR = 1.09 USD

Rates:
- Under 14 tonnes:
  - International/Overflight: 204.13 EUR + VSAT
  - Domestic: 84.99 EUR + VSAT
- Over 14 tonnes:
  - International/Overflight: 102.06 EUR + VSAT
  - Domestic: 66.34 EUR + VSAT

VSAT charge: $9.60 USD (converted to EUR)
"""


def calculate(distance, weight, context):
    """
    Calculate Chad overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    eur_to_usd = 1.09
    vsat_rate_usd = 9.60
    vsat_rate_eur = vsat_rate_usd / eur_to_usd

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Overflight (neither origin nor destination is Chad)
    if origin_country != "Chad" and destination_country != "Chad":
        if weight <= 14:
            cost = 204.13 + vsat_rate_eur
        else:
            cost = 102.06 + vsat_rate_eur
    # Domestic/International (one or both endpoints is Chad)
    else:
        if weight <= 14:
            cost = 84.99 + vsat_rate_eur
        else:
            cost = 66.34 + vsat_rate_eur

    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
