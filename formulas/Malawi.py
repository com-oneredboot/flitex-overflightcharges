"""
Malawi Overflight Charges Formula

Currency: USD

Rate: Fixed charge of $75
"""


def calculate(distance, weight, context):
    """Calculate Malawi overflight charges."""
    return {"cost": 75.0, "currency": "USD", "usd_cost": 75.0}
