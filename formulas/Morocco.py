"""
Morocco Overflight Charges Formula

Currency: EUR
Conversion: 1 EUR = 1.05 USD

Rate: 39.87 EUR (overflight only)

Formula:
- Overflight: 39.87 * sqrt(weight/50) * ((distance-20)/100)
- Domestic/International: $0
"""


def calculate(distance, weight, context):
    """Calculate Morocco overflight charges."""
    eur_to_usd = 1.05

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Overflight only
    if origin_country != "Morocco" and destination_country != "Morocco":
        unit_rate = 39.87
        distance_factor = (distance - 20) / 100
        mtow = sqrt(weight / 50)
        cost = unit_rate * mtow * distance_factor
        return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
    else:
        return {"cost": 0.00, "currency": "EUR", "usd_cost": 0.00}
