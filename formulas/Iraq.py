"""
Iraq Overflight Charges Formula

Currency: USD

Rate: Fixed charge of $450
"""


def calculate(distance, weight, context):
    """
    Calculate Iraq overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    overflight_rate = 450

    return {"cost": overflight_rate, "currency": "USD", "usd_cost": overflight_rate}
