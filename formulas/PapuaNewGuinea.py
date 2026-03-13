"""Papua New Guinea Overflight Charges Formula"""


def calculate(distance, weight, context):
    pgk_to_usd = 0.27
    calculated_cost = 15.0 * (distance / 100) * sqrt(weight)
    return {"cost": calculated_cost, "currency": "PGK", "usd_cost": calculated_cost * pgk_to_usd}
