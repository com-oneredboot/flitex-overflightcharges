"""
Mexico Overflight Charges Formula

Currency: MXN (Mexican Peso)
Conversion: 1 MXN = 0.058 USD

Rates (based on wingspan in meters):
- Up to 16.7m: 0.27 MXN per km
- 16.7-25m: 2.04 MXN per km
- 25-38m: 5.9 MXN per km
- Over 38m: 8.81 MXN per km

Note: Requires wingspan data (not available in standard context)
Using default rate of 5.9 MXN per km
"""


def calculate(distance, weight, context):
    """Calculate Mexico overflight charges."""
    mxn_to_usd = 0.058

    # Default to mid-range rate (would need wingspan from context)
    rate = 5.9
    calculated_cost = rate * distance

    return {
        "cost": calculated_cost,
        "currency": "MXN",
        "usd_cost": calculated_cost * mxn_to_usd,
    }
