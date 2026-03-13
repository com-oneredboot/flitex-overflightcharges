"""Senegal Overflight Charges Formula - Same as Madagascar/Niger"""


def calculate(distance, weight, context):
    eur_to_usd = 1.09
    vsat_rate_eur = 9.60 / eur_to_usd
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    if origin != "Senegal" and dest != "Senegal":
        cost = (211.69 if weight <= 14 else 105.84) + vsat_rate_eur
    else:
        cost = (88.14 if weight <= 14 else 68.80) + vsat_rate_eur
    return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
