"""Thailand Overflight Charges Formula"""


def calculate(distance, weight, context):
    thb_to_usd = 0.028
    rates = [
        (3, 9000), (10, 15000), (25, 18000), (50, 30000),
        (100, 45000), (200, 48000), (300, 54000), (400, 66000),
        (float("inf"), 78000),
    ]
    for tonnes, rate in rates:
        if weight < tonnes:
            return {"cost": rate, "currency": "THB", "usd_cost": rate * thb_to_usd}
