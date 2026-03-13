"""Uzbekistan Overflight Charges Formula"""


def calculate(distance, weight, context):
    eur_to_usd = 1.05
    cost = 25.54 * (distance / 100) * sqrt(weight / 50)
    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
