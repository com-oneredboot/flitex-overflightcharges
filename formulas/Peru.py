"""Peru Overflight Charges Formula"""


def calculate(distance, weight, context):
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    distance_km = distance * 1.852
    
    is_domestic = origin == "Peru" and dest == "Peru"
    is_international = origin == "Peru" or dest == "Peru"
    
    if is_domestic:
        if weight <= 5.7:
            rate = 0.16
        elif weight <= 10:
            rate = 0.31
        elif weight <= 35:
            rate = 0.34
        elif weight <= 70:
            rate = 0.46
        elif weight <= 105:
            rate = 0.69
        else:
            rate = 0.91
        cost = max(15.18, rate * distance_km)
        return {"cost": cost, "currency": "PEN", "usd_cost": cost}
    elif is_international:
        if weight <= 5.7:
            rate = 0.07
        elif weight <= 10:
            rate = 0.13
        elif weight <= 35:
            rate = 0.14
        elif weight <= 70:
            rate = 0.2
        elif weight <= 105:
            rate = 0.3
        else:
            rate = 0.4
        cost = max(7.05, rate * distance_km)
        return {"cost": cost, "currency": "USD", "usd_cost": cost}
    else:
        if weight <= 55:
            rate = 0.18
        elif weight <= 115:
            rate = 0.29
        elif weight <= 200:
            rate = 0.56
        else:
            rate = 0.84
        cost = rate * distance_km
        return {"cost": cost, "currency": "USD", "usd_cost": cost}
