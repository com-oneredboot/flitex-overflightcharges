"""
Liberia Overflight Charges Formula

Currency: USD

Rate: 0.81 USD per nautical mile

Formula:
- Cost = 0.81 * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Liberia overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    unit_rate = 0.81

    cost = unit_rate * distance

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
