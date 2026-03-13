"""
Japan Overflight Charges Formula

Currency: JPY (Japanese Yen)
Conversion: 1 JPY = 0.0069 USD

Rates:
- Domestic (distance-based, per tonne):
  - Up to 400 NM: 950 JPY
  - 400-800 NM: 1180 JPY
  - Over 800 NM: 1670 JPY

- International terminal (destination Japan):
  - Up to 100 tonnes: 180000 JPY
  - Over 100 tonnes: 207700 JPY

- Overflight:
  - Weight >= 15 tonnes: 89000 JPY
  - Weight < 15 tonnes: 0 JPY
"""


def calculate(distance, weight, context):
    """
    Calculate Japan overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    jpy_to_usd = 0.0069

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Japan" and destination_country == "Japan":
        if distance <= 400:
            rate = 950
        elif distance <= 800:
            rate = 1180
        else:
            rate = 1670

        cost = rate * (weight / 1000)  # Rate is per tonne, weight already in tonnes
        return {"cost": cost, "currency": "JPY", "usd_cost": cost * jpy_to_usd}

    # International terminal (destination Japan)
    if destination_country == "Japan":
        if weight <= 100:
            cost = 180000
        else:
            cost = 207700

        return {"cost": cost, "currency": "JPY", "usd_cost": cost * jpy_to_usd}

    # Overflight
    if weight >= 15:
        cost = 89000
    else:
        cost = 0

    return {"cost": cost, "currency": "JPY", "usd_cost": cost * jpy_to_usd}
