"""
Azerbaijan Overflight Charges Formula

Currency: EUR
Conversion: 1 EUR = 1.09 USD

Rates (weight-based, per 100 NM):
- Up to 50 tonnes: 35 EUR
- 50-100 tonnes: 45 EUR
- 100-200 tonnes: 55 EUR
- 200-300 tonnes: 60 EUR
- 300-400 tonnes: 70 EUR
- 400-500 tonnes: 75 EUR
- Over 500 tonnes: 80 EUR

Formula:
- Cost = rate * (distance / 100)
"""


def calculate(distance, weight, context):
    """
    Calculate Azerbaijan overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    eur_to_usd = 1.09

    distance_factor = distance / 100

    # Determine rate based on weight
    if weight <= 50:
        rate = 35.0
    elif weight <= 100:
        rate = 45.0
    elif weight <= 200:
        rate = 55.0
    elif weight <= 300:
        rate = 60.0
    elif weight <= 400:
        rate = 70.0
    elif weight <= 500:
        rate = 75.0
    else:
        rate = 80.0

    cost = rate * distance_factor

    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
