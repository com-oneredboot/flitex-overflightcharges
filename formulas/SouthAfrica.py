"""South Africa Overflight Charges Formula"""


def calculate(distance, weight, context):
    zar_to_usd = 0.053
    variable_cost = 32.96
    
    if weight <= 5:
        aerodrome_charge = variable_cost + (133.92) * (weight / 10) + 70.66
        tma_access_charge = variable_cost + (133.92) * (weight / 10) + 130.53
        area_charge = 0
        cost = aerodrome_charge + tma_access_charge + area_charge
    elif weight <= 15:
        aerodrome_charge = variable_cost + (133.92 * (weight / 10)) + (141.34 * (weight / 10))
        tma_access_charge = variable_cost + ((133.92 * (weight / 10)) + (26.11 * weight))
        area_charge = variable_cost + ((133.92 * (weight / 10)) + (18.73) * (weight / 100))
        cost = aerodrome_charge + tma_access_charge + area_charge
    else:
        aerodrome_charge = variable_cost + (163.99 * (sqrt(weight) / 100)) + (173.12 * (sqrt(weight) / 100))
        tma_access_charge = variable_cost + (163.99 * (sqrt(weight) / 100)) + (319.75 * (sqrt(weight) / 100))
        area_charge = variable_cost + (163.99 * (sqrt(weight) / 100)) + (229.54 * (sqrt(weight) / 10000))
        cost = aerodrome_charge + tma_access_charge + area_charge
    
    return {"cost": cost, "currency": "ZAR", "usd_cost": cost * zar_to_usd}
