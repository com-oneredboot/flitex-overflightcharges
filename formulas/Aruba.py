"""
Aruba Overflight Charges Formula

Currency: ANG (Netherlands Antillean Guilder)
Conversion: 1 ANG = 0.55 USD

Rates:
- Unit rate: 47.08 ANG

Formula:
- Cost = unit_rate * distance * sqrt(weight)
"""


def calculate(distance, weight, context):
    """
    Calculate Aruba overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    ang_to_usd = 0.55
    unit_rate = 47.08

    calculated_cost = unit_rate * distance * sqrt(weight)

    return {
        "cost": calculated_cost,
        "currency": "ANG",
        "usd_cost": calculated_cost * ang_to_usd,
    }
