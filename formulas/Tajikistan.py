"""Tajikistan Overflight Charges Formula"""


def calculate(distance, weight, context):
    distance_factor = (distance - 20) / 100
    if weight <= 50:
        rate = 70
    elif weight <= 100:
        rate = 96.3
    elif weight <= 200:
        rate = 118.8
    elif weight <= 300:
        rate = 125
    elif weight <= 400:
        rate = 128.4
    else:
        rate = 130.5
    cost = rate * distance_factor
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
