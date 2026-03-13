"""
Angola Overflight Charges Formula

Currency: USD

Rates:
- Unit rate: 49.5 USD

Formula:
- Cost = unit_rate * max(0, distance/100) * sqrt(weight/50)
"""


def calculate(distance, weight, context):
    """
    Calculate Angola overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    unit_rate = 49.5

    calculated_cost = unit_rate * max(0, (distance / 100)) * sqrt(weight / 50)

    return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
