"""
Indonesia Overflight Charges Formula

Currency: IDR (domestic), USD (international)
Conversion: 1 IDR = 0.000066 USD

Rates:
- Domestic: 350 IDR per 100 NM per tonne
- International: 0.55 USD per 100 NM per tonne

Formula:
- Cost = unit_rate * (distance/100) * weight
"""


def calculate(distance, weight, context):
    """
    Calculate Indonesia overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    idr_to_usd = 0.000066

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Indonesia" and destination_country == "Indonesia":
        domestic_unit_rate = 350
        calculated_cost = domestic_unit_rate * (distance / 100) * weight
        return {
            "cost": calculated_cost,
            "currency": "IDR",
            "usd_cost": calculated_cost * idr_to_usd,
        }

    # International/Overflight
    else:
        international_unit_rate = 0.55
        calculated_cost = international_unit_rate * (distance / 100) * weight
        return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
