"""
Fiji Overflight Charges Formula

Currency: FJD (Fijian Dollar)
Conversion: 1 FJD = 0.44 USD

Rates:
- Domestic: 3.45 FJD per 50 NM
- International: 5.87 FJD per 50 NM

Formula:
- Cost = rate * (distance / 50)
"""


def calculate(distance, weight, context):
    """
    Calculate Fiji overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    fjd_to_usd = 0.44

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    distance_factor = distance / 50

    if origin_country == "Fiji" and destination_country == "Fiji":
        cost = distance_factor * 3.45
    else:
        cost = distance_factor * 5.87

    return {"cost": cost, "currency": "FJD", "usd_cost": cost * fjd_to_usd}
