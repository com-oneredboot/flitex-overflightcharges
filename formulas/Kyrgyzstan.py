"""
Kyrgyzstan Overflight Charges Formula

Currency: KGS (domestic), USD (international)
Conversion: 1 KGS = 0.011 USD

Rates (per 100 NM, with 20 NM deduction):
- Domestic:
  - Up to 50 tonnes: 1590 KGS
  - 50-100 tonnes: 2275 KGS
  - 100-200 tonnes: 2790 KGS
  - 200-300 tonnes: 2840 KGS
  - 300-400 tonnes: 2900 KGS
  - Over 400 tonnes: 3000 KGS

- International/Overflight:
  - Up to 50 tonnes: $45
  - 50-100 tonnes: $64
  - 100-200 tonnes: $78
  - 200-300 tonnes: $80
  - 300-400 tonnes: $81
  - Over 400 tonnes: $84

Formula:
- Cost = rate * ((distance - 20) / 100)
"""


def calculate(distance, weight, context):
    """
    Calculate Kyrgyzstan overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    kgs_to_usd = 0.011

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    distance_factor = (distance - 20) / 100

    # Domestic flights
    if origin_country == "Kyrgyzstan" and destination_country == "Kyrgyzstan":
        if weight <= 50:
            rate = 1590.00
        elif weight <= 100:
            rate = 2275.00
        elif weight <= 200:
            rate = 2790.00
        elif weight <= 300:
            rate = 2840.00
        elif weight <= 400:
            rate = 2900.00
        else:
            rate = 3000.00

        overflight_cost = rate * distance_factor
        return {
            "cost": overflight_cost,
            "currency": "KGS",
            "usd_cost": overflight_cost * kgs_to_usd,
        }

    # International/Overflight
    else:
        if weight <= 50:
            rate = 45.0
        elif weight <= 100:
            rate = 64.0
        elif weight <= 200:
            rate = 78.0
        elif weight <= 300:
            rate = 80.0
        elif weight <= 400:
            rate = 81.0
        else:
            rate = 84.0

        overflight_cost = rate * distance_factor
        return {"cost": overflight_cost, "currency": "USD", "usd_cost": overflight_cost}
