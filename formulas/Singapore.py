"""Singapore Overflight Charges Formula"""


def calculate(distance, weight, context):
    unit_rate = 0.55
    
    if distance < 50:
        return {"cost": 0, "currency": "USD", "usd_cost": 0}
    elif distance < 150:
        distance_factor = 1
        weight_factor = weight / 3
        cost = distance_factor * unit_rate * weight_factor
    else:
        extra_distance_factor = (distance - 150) / 100
        weight_factor = weight / 3
        cost = extra_distance_factor * unit_rate * weight_factor
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
