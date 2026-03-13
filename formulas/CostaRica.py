"""
Costa Rica Overflight Charges Formula

Currency: USD

Rates (based on MTOW in kg):
- 5670-22000 kg: $0.14 per NM
- 22000-45000 kg: $0.31 per NM
- 45000-77000 kg: $0.40 per NM
- Over 77000 kg: $0.60 per NM

Formula:
- Cost = rate * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Costa Rica overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    # Convert weight from tonnes to kg
    mtow_kg = weight * 1000

    if 5670 <= mtow_kg <= 22000:
        rate = 0.14
    elif 22000 < mtow_kg <= 45000:
        rate = 0.31
    elif 45000 < mtow_kg <= 77000:
        rate = 0.4
    else:
        rate = 0.6

    cost = rate * distance

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
