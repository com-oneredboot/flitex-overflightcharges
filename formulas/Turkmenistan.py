"""Turkmenistan Overflight Charges Formula"""


def calculate(distance, weight, context):
    distance_factor = (distance - 20) / 100
    if weight <= 50:
        rate = 61.0
    elif weight <= 100:
        rate = 75.0
    elif weight <= 200:
        rate = 88.0
    elif weight <= 300:
        rate = 99.0
    elif weight <= 400:
        rate = 108.0
    else:
        rate = 122.0
    cost = rate * distance_factor
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
