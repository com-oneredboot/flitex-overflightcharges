"""
Australia Overflight Charges Formula

Currency: AUD (Australian Dollar)
Conversion: 1 AUD = 0.66 USD

Rates:
- Weight <= 20 tonnes: 0.9 * (distance/100) * weight
- Weight > 20 tonnes: 3.87 * (distance/100) * sqrt(weight)
"""


def calculate(distance, weight, context):
    """
    Calculate Australia overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    aud_to_usd = 0.66

    if weight <= 20:
        cost = 0.9 * (distance / 100) * weight
    else:
        cost = 3.87 * (distance / 100) * sqrt(weight)

    return {"cost": cost, "currency": "AUD", "usd_cost": cost * aud_to_usd}
