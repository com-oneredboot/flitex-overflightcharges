"""Seychelles Overflight Charges Formula"""


def calculate(distance, weight, context):
    unit_rate = 0.345
    rate = distance * unit_rate * sqrt(weight / 50)
    return {"cost": rate, "currency": "USD", "usd_cost": rate}
