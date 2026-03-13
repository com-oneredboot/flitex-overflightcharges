"""
Mauritius Overflight Charges Formula

Currency: MUR (Mauritian Rupee)
Conversion: 1 MUR = 0.022 USD

Rate: 8.07 MUR (only for distance > 150 NM)

Formula:
- Cost = 8.07 * distance * sqrt(weight/50) if distance > 150
- Cost = 0 if distance <= 150
"""


def calculate(distance, weight, context):
    """Calculate Mauritius overflight charges."""
    mur_to_usd = 0.022

    if distance > 150:
        cost = 8.07 * distance * sqrt(weight / 50)
        return {"cost": cost, "currency": "MUR", "usd_cost": cost * mur_to_usd}
    else:
        return {"cost": 0, "currency": "MUR", "usd_cost": 0}
