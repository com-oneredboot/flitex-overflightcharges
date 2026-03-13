"""Trinidad and Tobago Overflight Charges Formula"""


def calculate(distance, weight, context):
    rate = 33.28
    calculated_cost = rate * (distance / 100) * sqrt(weight / 50)
    return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
