"""Syria Overflight Charges Formula"""


def calculate(distance, weight, context):
    eur_to_usd = 1.09
    if weight <= 75:
        cost = 75
    elif weight <= 200:
        cost = 1 * weight
    else:
        cost = 1.25 * weight
    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
