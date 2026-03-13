"""
Kazakhstan Overflight Charges Formula

Currency: USD

Terminal/Navaid rates (per 100 NM, with 20 NM deduction):
- Up to 50 tonnes: $49
- 50-100 tonnes: $66
- 100-200 tonnes: $82
- 200-300 tonnes: $89
- Over 300 tonnes: $93

Formula:
- Cost = rate * ((distance - 20) / 100)
"""


def calculate(distance, weight, context):
    """
    Calculate Kazakhstan overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    distance_factor = (distance - 20) / 100

    if weight <= 50:
        rate = 49.0
    elif weight <= 100:
        rate = 66.0
    elif weight <= 200:
        rate = 82.0
    elif weight <= 300:
        rate = 89.0
    else:
        rate = 93.0

    cost = rate * distance_factor

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
