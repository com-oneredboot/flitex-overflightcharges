"""
Laos Overflight Charges Formula

Currency: USD

Journey rates (weight-based flat charges):
- Up to 7 tonnes: $50
- 7-20 tonnes: $100
- 20-50 tonnes: $140
- 50-100 tonnes: $210
- 100-150 tonnes: $230
- 150-200 tonnes: $260
- 200-250 tonnes: $300
- 250-300 tonnes: $320
- Over 300 tonnes: $360
"""


def calculate(distance, weight, context):
    """
    Calculate Laos overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    if weight <= 7:
        cost = 50
    elif weight <= 20:
        cost = 100
    elif weight <= 50:
        cost = 140
    elif weight <= 100:
        cost = 210
    elif weight <= 150:
        cost = 230
    elif weight <= 200:
        cost = 260
    elif weight <= 250:
        cost = 300
    elif weight <= 300:
        cost = 320
    else:
        cost = 360

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
