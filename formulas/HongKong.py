"""
Hong Kong Overflight Charges Formula

Currency: HKD (Hong Kong Dollar)
Conversion: 1 HKD = 0.13 USD

Rate: 5.0 HKD per nautical mile

Formula:
- Cost = 5.0 * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Hong Kong overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    hkd_to_usd = 0.13

    cost = 5.0 * distance

    return {"cost": cost, "currency": "HKD", "usd_cost": cost * hkd_to_usd}
