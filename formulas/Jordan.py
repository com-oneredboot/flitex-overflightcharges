"""
Jordan Overflight Charges Formula

Currency: JOD (Jordanian Dinar)
Conversion: 1 JOD = 1.41 USD

Rate: 1 JOD per tonne, minimum $40

Formula:
- Cost = 1 * weight, minimum 40
"""


def calculate(distance, weight, context):
    """
    Calculate Jordan overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    jod_to_usd = 1.41
    minimum_charge = 40

    cost = 1 * weight
    calculated_cost = max(cost, minimum_charge)

    return {
        "cost": calculated_cost,
        "currency": "JOD",
        "usd_cost": calculated_cost * jod_to_usd,
    }
