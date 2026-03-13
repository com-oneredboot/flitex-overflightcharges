"""
Mozambique Overflight Charges Formula

Currency: USD

Overflight rates (weight-based flat charges):
- Up to 5.7 tonnes: $23
- 5.7-30 tonnes: $56
- 30-43 tonnes: $162
- 43-100 tonnes: $280
- 100-190 tonnes: $342
- 190-300 tonnes: $435
- Over 300 tonnes: $540
"""


def calculate(distance, weight, context):
    """Calculate Mozambique overflight charges."""
    if weight <= 5.7:
        cost = 23.0
    elif weight <= 30:
        cost = 56.0
    elif weight <= 43:
        cost = 162.0
    elif weight <= 100:
        cost = 280.0
    elif weight <= 190:
        cost = 342.0
    elif weight <= 300:
        cost = 435.0
    else:
        cost = 540.0

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
