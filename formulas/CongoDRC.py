"""
Congo DRC Overflight Charges Formula

Currency: USD

Rates:
- Distance <= 245 NM: 25.0 USD per 100 NM
- Distance > 245 NM: 48.0 USD per 100 NM

Formula:
- Cost = rate * (distance/100) * sqrt(weight/50)
"""


def calculate(distance, weight, context):
    """
    Calculate Congo DRC overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    if distance <= 245:
        rate = 25.0
    else:
        rate = 48.0

    cost = rate * (distance / 100) * sqrt(weight / 50)

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
