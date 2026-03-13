"""
French Guiana Overflight Charges Formula

Currency: EUR
Conversion: 1 EUR = 1.09 USD

Rate: 35.78 EUR

Formula:
- Cost = 35.78 * (distance/100) * sqrt(weight/50)
"""


def calculate(distance, weight, context):
    """
    Calculate French Guiana overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    eur_to_usd = 1.09

    calculated_cost = 35.78 * (distance / 100) * sqrt(weight / 50)

    return {
        "cost": calculated_cost,
        "currency": "EUR",
        "usd_cost": calculated_cost * eur_to_usd,
    }
