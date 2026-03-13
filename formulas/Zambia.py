"""Zambia Overflight Charges Formula"""


def calculate(distance, weight, context):
    km_to_nm = 0.539957
    vsat_charge = 9.60
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    distance_nm = distance * km_to_nm
    distance_factor = (distance_nm - 20) / 100
    weight_factor = round(pow(weight / 50, 0.7), 2)
    
    if origin == "Zambia" and dest == "Zambia":
        cost = (12 * 0.15 * distance_factor * weight_factor) + vsat_charge
    else:
        cost = (12 * distance_factor * weight_factor) + vsat_charge
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
