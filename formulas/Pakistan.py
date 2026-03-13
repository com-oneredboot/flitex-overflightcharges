"""Pakistan Overflight Charges Formula"""


def calculate(distance, weight, context):
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    if weight <= 5:
        rate = 0
    elif weight <= 40:
        rate = 0.44
    elif weight <= 120:
        rate = 0.58
    elif weight <= 250:
        rate = 0.88
    elif weight <= 350:
        rate = 1.0
    elif weight <= 450:
        rate = 1.14
    else:
        rate = 1.3
    
    if origin == "Pakistan" and dest == "Pakistan":
        cost = rate * distance
    else:
        cost = rate * (distance - 20)
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
