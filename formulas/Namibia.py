"""
Namibia Overflight Charges Formula

Currency: NAD (Namibian Dollar)
Conversion: 1 NAD = 0.052 USD

Rates:
- MTOW <= 5700 kg: 0.02 * sqrt(mtow_kg) * distance
- MTOW > 5700 kg: 0.055 * sqrt(mtow_kg) * distance
"""


def calculate(distance, weight, context):
    """Calculate Namibia overflight charges."""
    nad_to_usd = 0.052

    mtow_kg = weight * 1000

    if mtow_kg <= 5700:
        calculated_cost = 0.02 * sqrt(mtow_kg) * distance
    else:
        calculated_cost = 0.055 * sqrt(mtow_kg) * distance

    return {
        "cost": calculated_cost,
        "currency": "NAD",
        "usd_cost": calculated_cost * nad_to_usd,
    }
