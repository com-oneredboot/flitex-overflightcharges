"""Spain Overflight Charges Formula"""


def calculate(distance, weight, context):
    eur_to_usd = 1.05
    canaries_rate = 43.74
    weight_factor = sqrt(weight / 50)
    distance_factor = (distance - 20) / 100
    cost = canaries_rate * weight_factor * distance_factor
    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
