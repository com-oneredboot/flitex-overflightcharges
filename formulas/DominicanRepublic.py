"""
Dominican Republic Overflight Charges Formula

Currency: USD

Rates (weight-based flat charges in kg):
- Up to 25000 kg: $60
- 25000-60000 kg: $95
- 60000-100000 kg: $165
- 100000-200000 kg: $215
- Over 200000 kg: $350
"""


def calculate(distance, weight, context):
    """
    Calculate Dominican Republic overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    # Convert weight from tonnes to kg
    kilogram_weight = weight * 1000

    if kilogram_weight <= 25000:
        cost = 60
    elif kilogram_weight <= 60000:
        cost = 95
    elif kilogram_weight <= 100000:
        cost = 165
    elif kilogram_weight <= 200000:
        cost = 215
    else:
        cost = 350

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
