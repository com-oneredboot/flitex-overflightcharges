"""Portugal Overflight Charges Formula"""


def calculate(distance, weight, context):
    eur_to_usd = 1.10
    fir_name = context.get("firName", "")
    
    if "LISBOA" in fir_name.upper():
        unit_rate = 38.13
    elif "MARIA" in fir_name.upper():
        unit_rate = 7.91
    else:
        unit_rate = 38.13
    
    calculated_cost = unit_rate * max(0, (distance - 20) / 100) * sqrt(weight / 50)
    return {"cost": calculated_cost, "currency": "EUR", "usd_cost": calculated_cost * eur_to_usd}
