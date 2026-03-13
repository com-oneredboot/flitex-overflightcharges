"""Panama Overflight Charges Formula"""


def calculate(distance, weight, context):
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    is_takeoff_landing = "Panama" in origin or "Panama" in dest
    
    if is_takeoff_landing:
        if weight <= 50:
            rate = 0.3019
        elif weight <= 120:
            rate = 0.3397
        else:
            rate = 0.3774
    else:
        if weight <= 50:
            rate = 0.5949
        elif weight <= 120:
            rate = 0.6185
        else:
            rate = 0.6421
    
    weight_per_100_tonnes = weight / 100
    calculated_cost = rate * weight_per_100_tonnes * distance
    
    return {"cost": max(calculated_cost, 30.0), "currency": "PAB", "usd_cost": calculated_cost}
