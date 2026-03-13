"""
Israel Overflight Charges Formula

Currency: USD

Transit Air Traffic Control Fee (weight-based):
- Up to 50 tonnes: $108.74
- 50-100 tonnes: $129.13
- 100-150 tonnes: $169.91
- 150-200 tonnes: $197.10
- 200-300 tonnes: $231.08
- Over 300 tonnes: $278.65
"""


def calculate(distance, weight, context):
    """
    Calculate Israel overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    if weight <= 50:
        cost = 108.74
    elif weight <= 100:
        cost = 129.13
    elif weight <= 150:
        cost = 169.91
    elif weight <= 200:
        cost = 197.1
    elif weight <= 300:
        cost = 231.08
    else:
        cost = 278.65

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
