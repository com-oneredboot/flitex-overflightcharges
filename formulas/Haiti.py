"""
Haiti Overflight Charges Formula

Currency: USD

Rate: 13.96 USD

Formula:
- Cost = 13.96 * sqrt(weight)
"""


def calculate(distance, weight, context):
    """
    Calculate Haiti overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    rate = 13.96

    calculated_cost = rate * sqrt(weight)

    return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
