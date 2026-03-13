"""Suriname Overflight Charges Formula"""


def calculate(distance, weight, context):
    srd_to_usd = 0.027
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    if origin != "Suriname" and dest != "Suriname":
        if weight <= 10:
            cost = 25
        elif weight <= 50:
            cost = 125
        else:
            cost = 250
        return {"cost": cost, "currency": "USD", "usd_cost": cost}
    
    return {"cost": 5000, "currency": "SRD", "usd_cost": 5000 * srd_to_usd}
