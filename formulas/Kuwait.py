"""
Kuwait Overflight Charges Formula

Currency: KWD (Kuwaiti Dinar)
Conversion: 1 KWD = 3.23 USD

Rate: Fixed charge of 40 KWD
"""


def calculate(distance, weight, context):
    """
    Calculate Kuwait overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    kwd_to_usd = 3.23

    return {"cost": 40.0, "currency": "KWD", "usd_cost": 40.0 * kwd_to_usd}
