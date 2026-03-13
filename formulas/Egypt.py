"""
Egypt Overflight Charges Formula

Currency: EUR
Conversion: 1 EUR = 1.09 USD

Rate: 17.03 EUR

Formula:
- Cost = 17.03 * ((distance-20)/100) * sqrt(weight/50)
"""


def calculate(distance, weight, context):
    """
    Calculate Egypt overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    eur_to_usd = 1.09

    cost = 17.03 * ((distance - 20) / 100) * sqrt(weight / 50)

    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
