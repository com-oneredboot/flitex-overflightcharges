"""Sri Lanka Overflight Charges Formula"""


def calculate(distance, weight, context):
    if weight <= 90:
        cost = 100
    elif weight <= 175:
        cost = 150
    elif weight <= 260:
        cost = 200
    else:
        cost = 250
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
