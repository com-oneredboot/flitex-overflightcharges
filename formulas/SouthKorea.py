"""South Korea Overflight Charges Formula"""


def calculate(distance, weight, context):
    krw_to_usd = 0.00076
    landing_surcharge = 5820
    overflight_surcharge = 1980
    rate_jet = 157210
    
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    if dest == "South Korea":
        cost = rate_jet + landing_surcharge
    elif origin != "South Korea" and dest != "South Korea":
        cost = rate_jet + overflight_surcharge
    else:
        cost = rate_jet
    
    return {"cost": cost, "currency": "KRW", "usd_cost": cost * krw_to_usd}
