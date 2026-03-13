"""
Iran Overflight Charges Formula

Currency: USD

Rates:
- International: 0.00406 * weight * distance, minimum $100
- Domestic: 0.00406 * weight * distance * 0.26

Formula:
- Cost = unit_rate * weight * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Iran overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    international_unit_rate = 0.00406
    minimum_charge = 100

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Iran" and destination_country == "Iran":
        cost = international_unit_rate * weight * distance * 0.26
        return {"cost": cost, "currency": "USD", "usd_cost": cost}

    # International/Overflight
    else:
        cost = international_unit_rate * weight * distance
        cost = max(cost, minimum_charge)
        return {"cost": cost, "currency": "USD", "usd_cost": cost}
