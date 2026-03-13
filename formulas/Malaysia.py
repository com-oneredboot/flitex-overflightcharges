"""
Malaysia Overflight Charges Formula

Currency: MYR (Malaysian Ringgit)
Conversion: 1 MYR = 0.21 USD

Rates (per NM, minimum $10):
- Up to 2.5 tonnes: 0.1 MYR
- 2.5-5 tonnes: 0.2 MYR
- 5-45 tonnes: 0.3 MYR
- 45-90 tonnes: 0.4 MYR
- 90-135 tonnes: 0.5 MYR
- Over 135 tonnes: 0.6 MYR
"""


def calculate(distance, weight, context):
    """Calculate Malaysia overflight charges."""
    myr_to_usd = 0.21

    if weight <= 2.5:
        rate = 0.1
    elif weight <= 5:
        rate = 0.2
    elif weight <= 45:
        rate = 0.3
    elif weight <= 90:
        rate = 0.4
    elif weight <= 135:
        rate = 0.5
    else:
        rate = 0.6

    temp = rate * distance
    cost = max(temp, 10.0)

    return {"cost": cost, "currency": "MYR", "usd_cost": cost * myr_to_usd}
