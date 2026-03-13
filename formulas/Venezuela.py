"""Venezuela Overflight Charges Formula"""


def calculate(distance, weight, context):
    cost = 0.0018 * 0.5 * (weight - 75) * distance
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
