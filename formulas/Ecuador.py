"""
Ecuador Overflight Charges Formula

Currency: USD

Rate: 0.1054 USD

Formula:
- Cost = unit_rate * sqrt(weight) * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Ecuador overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    rate = 0.1054

    calculated_cost = rate * sqrt(weight) * distance

    return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
