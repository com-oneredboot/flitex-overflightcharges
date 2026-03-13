"""Solomon Islands Overflight Charges Formula"""


def calculate(distance, weight, context):
    sbd_to_usd = 0.12
    unit_rate_per_100km = 5
    calculated_cost = (distance / 100) * unit_rate_per_100km
    return {"cost": calculated_cost, "currency": "SBD", "usd_cost": calculated_cost * sbd_to_usd}
