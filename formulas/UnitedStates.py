"""United States Overflight Charges Formula"""


def calculate(distance, weight, context):
    en_route_rate = 61.75
    oceanic_rate = 26.51
    
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    origin_fir_tag = context.get("originFirTag")
    dest_fir_tag = context.get("destinationFirTag")
    fir_tag = context.get("firTag")
    
    # No charge for US origin or destination
    if origin == "United States" or dest == "United States":
        return {"cost": 0.00, "currency": "USD", "usd_cost": 0.00}
    
    # Determine rate based on FIR
    rate = en_route_rate if (origin_fir_tag == fir_tag or dest_fir_tag == fir_tag) else oceanic_rate
    cost = (distance / 100) * rate
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
