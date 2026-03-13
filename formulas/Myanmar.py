"""
Myanmar Overflight Charges Formula

Currency: MMK (domestic), USD (international)
Conversion: 1 MMK = 0.00047 USD

Rates:
- Domestic (MMK): 6300-106800 based on weight
- International (USD): 32-609 based on weight
"""


def calculate(distance, weight, context):
    """Calculate Myanmar overflight charges."""
    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Myanmar" and destination_country == "Myanmar":
        if weight <= 25:
            cost = 6300.0
        elif weight <= 50:
            cost = 10400.0
        elif weight <= 75:
            cost = 15500.0
        elif weight <= 100:
            cost = 20900.0
        elif weight <= 200:
            cost = 53500.0
        elif weight <= 300:
            cost = 80150.0
        else:
            cost = 106800.0

        return {"cost": cost, "currency": "MMK", "usd_cost": cost * 0.00047}

    # International/Overflight
    else:
        if weight <= 25:
            cost = 32
        elif weight <= 50:
            cost = 53
        elif weight <= 75:
            cost = 99
        elif weight <= 100:
            cost = 119
        elif weight <= 200:
            cost = 304
        elif weight <= 300:
            cost = 457
        else:
            cost = 609

        return {"cost": cost, "currency": "USD", "usd_cost": cost}
