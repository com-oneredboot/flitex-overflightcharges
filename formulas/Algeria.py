"""
Algeria Overflight Charges Formula

Currency: DZD (Algerian Dinar)
Conversion: 1 DZD = 0.0074 USD

Rates:
- Unit rate: 4636 DZD

Formula:
- Weight factor: sqrt(weight / 50)
- Distance factor: (distance - 20) / 100
- Cost = unit_rate * weight_factor * distance_factor
"""


def calculate(distance, weight, context):
    """
    Calculate Algeria overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    dzd_to_usd = 0.0074
    unit_rate = 4636

    weight_factor = sqrt(weight / 50)
    distance_factor = (distance - 20) / 100

    cost_dzd = unit_rate * weight_factor * distance_factor

    return {"cost": cost_dzd, "currency": "DZD", "usd_cost": cost_dzd * dzd_to_usd}
