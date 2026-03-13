"""
Ghana Overflight Charges Formula

Currency: USD

Rates:
- Weight <= 20 tonnes: $200 flat
- Weight > 20 tonnes: $0.75 per NM (min $200, max $600)
"""


def calculate(distance, weight, context):
    """
    Calculate Ghana overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    if weight <= 20:
        cost = 200.00
    else:
        temp = 0.75 * distance
        if temp < 200:
            cost = 200
        elif temp > 600:
            cost = 600
        else:
            cost = temp

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
