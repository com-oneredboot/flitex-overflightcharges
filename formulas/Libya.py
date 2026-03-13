"""
Libya Overflight Charges Formula

Currency: LYD (Libyan Dinar)
Conversion: 1 LYD = 0.20 USD

Overflight rates (weight-based flat charges):
- Up to 5 tonnes: 54 LYD
- 5-100 tonnes: 378 LYD
- 100-200 tonnes: 540 LYD
- 200-300 tonnes: 675 LYD
- Over 300 tonnes: 900 LYD
"""


def calculate(distance, weight, context):
    """
    Calculate Libya overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    lyd_to_usd = 0.20

    if weight <= 5:
        cost = 54.0
    elif weight <= 100:
        cost = 378
    elif weight <= 200:
        cost = 540
    elif weight <= 300:
        cost = 675
    else:
        cost = 900

    return {"cost": cost, "currency": "LYD", "usd_cost": cost * lyd_to_usd}
