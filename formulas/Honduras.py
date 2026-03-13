"""
Honduras Overflight Charges Formula

Currency: USD

Rates (based on MTOW in kg):
- Up to 5670 kg: $0
- 5670-22000 kg: $0.20 per NM
- 22000-45000 kg: $0.33 per NM
- 45000-77000 kg: $0.47 per NM
- Over 77000 kg: $0.64 per NM

Formula:
- Cost = rate * distance
"""


def calculate(distance, weight, context):
    """
    Calculate Honduras overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    # Convert weight from tonnes to kg
    weight_kg = weight * 1000

    if weight_kg <= 5670:
        rate = 0
    elif weight_kg <= 22000:
        rate = 0.2
    elif weight_kg <= 45000:
        rate = 0.33
    elif weight_kg <= 77000:
        rate = 0.47
    else:
        rate = 0.64

    calculated_cost = rate * distance

    return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
