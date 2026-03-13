"""Sudan Overflight Charges Formula"""


def calculate(distance, weight, context):
    chf_to_usd = 1.12
    nafisat_charge = 10
    
    if weight <= 50:
        rate = 1800
    elif weight <= 200:
        rate = 2400.00
    else:
        rate = 2700.00
    
    calculated_cost = rate + (nafisat_charge / chf_to_usd)
    return {"cost": calculated_cost, "currency": "CHF", "usd_cost": calculated_cost * chf_to_usd}
