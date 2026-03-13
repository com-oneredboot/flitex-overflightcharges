"""Saudi Arabia Overflight Charges Formula"""


def calculate(distance, weight, context):
    sar_to_usd = 0.27
    cost = 118.0 * sqrt(weight / 50) * (distance / 100)
    return {"cost": cost, "currency": "SAR", "usd_cost": cost * sar_to_usd}
