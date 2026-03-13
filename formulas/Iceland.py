"""
Iceland Overflight Charges Formula

Currency: GBP (British Pound)
Conversion: 1 GBP = 1.275 USD (based on 118.09 GBP = 150.62 USD)

Rate: Fixed charge of 118.09 GBP
"""


def calculate(distance, weight, context):
    """
    Calculate Iceland overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    return {"cost": 118.09, "currency": "GBP", "usd_cost": 150.62}
