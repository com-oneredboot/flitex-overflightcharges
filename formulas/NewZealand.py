"""
New Zealand Overflight Charges Formula

Currency: NZD (New Zealand Dollar)
Conversion: 1 NZD = 0.61 USD

Rates:
- Domestic: distance * 0.12573 + (0.41751 * sqrt(weight-2) * (distance/100))
- International: 150 * 0.12573 (fixed)
"""


def calculate(distance, weight, context):
    """Calculate New Zealand overflight charges."""
    nzd_to_usd = 0.61

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "New Zealand" and destination_country == "New Zealand":
        domestic_enroute_base_charge = 0.12573
        domestic_weight_charge = 0.41751

        rate = distance * domestic_enroute_base_charge + (
            domestic_weight_charge * sqrt(weight - 2) * (distance / 100)
        )
    # International/Overflight
    else:
        domestic_enroute_base_charge = 0.12573
        rate = 150 * domestic_enroute_base_charge

    return {"cost": rate, "currency": "NZD", "usd_cost": rate * nzd_to_usd}
