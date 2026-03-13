"""
Nepal Overflight Charges Formula

Currency: MMK (domestic), USD (international)
Conversion: 1 MMK = 0.00047 USD

Rates:
- Domestic: International rates * 0.4
- International: 45.9-305.5 USD based on weight
"""


def calculate(distance, weight, context):
    """Calculate Nepal overflight charges."""
    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Determine base rate
    if weight <= 25:
        rate = 45.9
    elif weight <= 50:
        rate = 76.5
    elif weight <= 75:
        rate = 152.75
    else:
        rate = 305.5

    # Domestic flights (using Myanmar check from source - likely error)
    if origin_country == "Myanmar" and destination_country == "Myanmar":
        calculated_cost = rate * 0.4
        return {"cost": calculated_cost, "currency": "MMK", "usd_cost": calculated_cost * 0.00047}

    # International/Overflight
    else:
        return {"cost": rate, "currency": "USD", "usd_cost": rate}
