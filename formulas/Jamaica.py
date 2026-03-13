"""
Jamaica Overflight Charges Formula

Currency: USD

Rates (weight-based flat charges):
- Up to 5.7 tonnes: $0
- 5.7-15 tonnes: $72
- Over 15 tonnes: $160
"""


def calculate(distance, weight, context):
    """
    Calculate Jamaica overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    if weight <= 5.7:
        cost = 0.0
    elif weight <= 15:
        cost = 72.0
    else:
        cost = 160.0

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
