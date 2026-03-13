"""Vietnam Overflight Charges Formula"""


def calculate(distance, weight, context):
    if distance <= 500:
        rates = [
            (20, 115), (50, 176), (100, 255), (150, 330),
            (190, 384), (240, 420), (300, 450), (float("inf"), 480),
        ]
    else:
        rates = [
            (20, 129), (50, 197), (100, 286), (150, 370),
            (190, 431), (240, 460), (300, 490), (float("inf"), 520),
        ]
    for tonnes, rate in rates:
        if weight <= tonnes:
            return {"cost": rate, "currency": "USD", "usd_cost": rate}
