"""Oman Overflight Charges Formula"""


def calculate(distance, weight, context):
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    if weight <= 49:
        rate = 152
    elif weight <= 100:
        rate = 202
    elif weight <= 200:
        rate = 252
    else:
        rate = 327
    
    if origin != "Oman" and dest != "Oman":
        cost = rate
    else:
        cost = rate * 0.5
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
