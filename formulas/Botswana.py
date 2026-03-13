"""
Botswana Overflight Charges Formula

Currency: USD

Rates:
- Weight <= 2.5 tonnes: $15.50 flat
- 2.5 < weight <= 5.7 tonnes: $20.65 flat
- Weight > 5.7 tonnes: 20.65 * (distance/100) * sqrt(weight/20)
"""


def calculate(distance, weight, context):
    """
    Calculate Botswana overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    if weight <= 2.5:
        cost = 15.5
    elif weight <= 5.7:
        cost = 20.65
    else:
        cost = 20.65 * (distance / 100) * sqrt(weight / 20)

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
