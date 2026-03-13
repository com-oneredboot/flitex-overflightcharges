"""Russia Overflight Charges Formula"""


def calculate(distance, weight, context):
    if weight <= 2:
        rate = 11.1
    elif weight <= 5:
        rate = 17.1
    elif weight <= 20:
        rate = 31.7
    elif weight <= 50:
        rate = 74.1
    elif weight <= 100:
        rate = 99.8
    elif weight <= 200:
        rate = 123.9
    elif weight <= 300:
        rate = 128.5
    elif weight <= 400:
        rate = 131.5
    else:
        rate = 134.6
    
    cost = rate * (distance / 100)
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
