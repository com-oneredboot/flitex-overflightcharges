"""
Mongolia Overflight Charges Formula

Currency: USD

Rates (per 100 NM):
- Up to 50 tonnes: $32
- 50-100 tonnes: $45
- 100-200 tonnes: $64
- 200-300 tonnes: $70
- Over 300 tonnes: $79
"""


def calculate(distance, weight, context):
    """Calculate Mongolia overflight charges."""
    if weight <= 50:
        rate = 32.00
    elif weight <= 100:
        rate = 45.00
    elif weight <= 200:
        rate = 64.00
    elif weight <= 300:
        rate = 70.00
    else:
        rate = 79.00

    usd_cost = rate * (distance / 100)

    return {"cost": usd_cost, "currency": "USD", "usd_cost": usd_cost}
