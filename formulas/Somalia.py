"""Somalia Overflight Charges Formula"""


def calculate(distance, weight, context):
    if weight <= 20:
        cost = 100.00
    else:
        cost = 275.00
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
