"""Philippines Overflight Charges Formula"""


def calculate(distance, weight, context):
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    if weight <= 20:
        rate = 7
    elif weight <= 50:
        rate = 14
    elif weight <= 100:
        rate = 20
    elif weight <= 200:
        rate = 28
    elif weight <= 300:
        rate = 36
    else:
        rate = 43
    
    if origin == "Philippines" and dest == "Philippines":
        cost = (distance / 100) * rate
    else:
        cost = (distance / 100) * rate * 0.5
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
