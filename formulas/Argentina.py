"""
Argentina Overflight Charges Formula

Currency: ARS (domestic), USD (international/overflight)
Conversion: 1 ARS = 0.0039 USD

Rates:
- Domestic: 0.0237 ARS per tonne per NM
- International/Overflight: Weight-based unit rates

Logic:
- Domestic (both origin and destination Argentina): unit_rate * weight * distance
- International (one endpoint Argentina): tiered rates based on weight
- Overflight (neither endpoint Argentina): tiered rates based on weight
"""


def calculate(distance, weight, context):
    """
    Calculate Argentina overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    ars_to_usd = 0.0039

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Argentina" and destination_country == "Argentina":
        unit_rate = 0.0237
        cost = unit_rate * weight * distance
        return {"cost": cost, "currency": "ARS", "usd_cost": cost * ars_to_usd}

    # International flights (one endpoint is Argentina)
    elif origin_country == "Argentina" or destination_country == "Argentina":
        if weight <= 20:
            unit_rate = 0.066
        elif weight <= 40:
            unit_rate = 0.088
        elif weight <= 100:
            unit_rate = 0.11
        else:
            unit_rate = 0.122

        cost = unit_rate * sqrt(weight) * distance
        return {"cost": cost, "currency": "USD", "usd_cost": cost}

    # Overflights (neither endpoint is Argentina)
    else:
        if weight <= 20:
            unit_rate = 0.066
        elif weight <= 40:
            unit_rate = 0.088
        elif weight <= 100:
            unit_rate = 0.11
        else:
            unit_rate = 0.122

        cost = unit_rate * sqrt(weight) * distance
        return {"cost": cost, "currency": "USD", "usd_cost": cost}
