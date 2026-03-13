"""UK Overflight Charges Formula"""


def calculate(distance, weight, context):
    fir_name = context.get("firName", "")
    if "OCEANIC" in fir_name.upper():
        return {"cost": 45.0, "currency": "GBP", "usd_cost": 57.38}
    else:
        unit_rate = 55.257
        calculated_cost = unit_rate * ((distance - 20) / 100) * sqrt(weight / 50)
        return {"cost": calculated_cost, "currency": "GBP", "usd_cost": calculated_cost * 1.28}
