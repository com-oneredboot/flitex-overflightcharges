"""
Maldives Overflight Charges Formula

Currency: USD

Rates:
- Domestic: Terminal/Navaid only (25-63 USD based on weight)
- International: Terminal/Navaid (50-125 USD) + Overflight (125-313 USD)
"""


def calculate(distance, weight, context):
    """Calculate Maldives overflight charges."""
    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Maldives" and destination_country == "Maldives":
        if weight <= 90:
            cost = 25
        elif weight <= 175:
            cost = 38
        elif weight <= 260:
            cost = 50
        else:
            cost = 63
    # International/Overflight
    else:
        # Terminal/Navaid
        if weight <= 90:
            cost = 50
        elif weight <= 175:
            cost = 75
        elif weight <= 260:
            cost = 100
        else:
            cost = 125

    return {"cost": cost, "currency": "USD", "usd_cost": cost}
