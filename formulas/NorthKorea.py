"""North Korea Overflight Charges Formula"""


def calculate(distance, weight, context):
    eur_to_usd = 1.09
    meteo_charge = 50
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    if origin == "North Korea" and dest == "North Korea":
        rates = [(50, 190), (100, 265), (200, 355), (250, 440), (300, 535), (float("inf"), 590)]
    else:
        rates = [(90, 235), (150, 290), (200, 405), (250, 500), (300, 610), (float("inf"), 685)]
    for tonnes, rate in rates:
        if weight <= tonnes:
            cost = rate + meteo_charge
            return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
