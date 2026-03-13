"""
Belize Overflight Charges Formula

Currency: USD

Rates (based on MTOW in kg):
- 5670-22000 kg: $0.20 per NM
- 22000-45000 kg: $0.33 per NM
- 45000-77000 kg: $0.47 per NM
- Over 77000 kg: $0.64 per NM

Formula:
- Cost = rate * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Belize overflight charges.

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
        cost = 0.2 * distance
    elif 22000 < mtow_kg <= 45000:
        cost = 0.33 * distance
    elif 45000 < mtow_kg <= 77000:
        cost = 0.47 * distance
    elif mtow_kg > 77000:
        cost = 0.64 * distance
    else:
        cost = 0

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
