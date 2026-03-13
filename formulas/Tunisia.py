"""Tunisia Overflight Charges Formula"""


def calculate(distance, weight, context):
    eur_to_usd = 1.05
    if weight <= 5:
        cost = 45.00
    elif weight <= 24:
        cost = 115.00
    elif weight <= 40:
        cost = 180.00
    else:
        cost = 315.00
    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
