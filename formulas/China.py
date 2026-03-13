"""
China Overflight Charges Formula

Currency: CNY (Chinese Yuan)
Conversion: 1 CNY = 0.14 USD

Rates (per km, with 20 km deduction):
- Up to 25 tonnes: 1.5 CNY
- 25-50 tonnes: 3.0 CNY
- 50-100 tonnes: 3.4 CNY
- 100-200 tonnes: 3.8 CNY
- Over 200 tonnes: 233 * ((distance-20)/100) * sqrt(weight/50)

Formula:
- Cost = rate * (distance - 20) for weight <= 200 tonnes
- Cost = 233 * ((distance-20)/100) * sqrt(weight/50) for weight > 200 tonnes
"""


def calculate(distance, weight, context):
    """
    Calculate China overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    cny_to_usd = 0.14

    if weight <= 25:
        cost = 1.5 * (distance - 20)
    elif weight <= 50:
        cost = 3.0 * (distance - 20)
    elif weight <= 100:
        cost = 3.4 * (distance - 20)
    elif weight <= 200:
        cost = 3.8 * (distance - 20)
    else:
        cost = 233.0 * ((distance - 20) / 100) * sqrt(weight / 50)

    return {"cost": cost, "currency": "CNY", "usd_cost": cost * cny_to_usd}
