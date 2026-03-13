"""
Bahrain Overflight Charges Formula

Currency: BHD (Bahraini Dinar)
Conversion: 1 BHD = 2.65 USD

Rates (weight-based, for overflights only):
- Up to 40 tonnes: 24.0 BHD
- 40-80 tonnes: 35.0 BHD
- 80-120 tonnes: 47.0 BHD
- 120-200 tonnes: 59.0 BHD
- 200-300 tonnes: 71.0 BHD
- Over 300 tonnes: 79.0 BHD

Note: Only applies to overflights (neither origin nor destination is Bahrain)
"""


def calculate(distance, weight, context):
    """
    Calculate Bahrain overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    bhd_to_usd = 2.65

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Only charge for overflights
    if origin_country != "Bahrain" and destination_country != "Bahrain":
        if weight < 40:
            cost = 24.0
        elif weight < 80:
            cost = 35.0
        elif weight < 120:
            cost = 47.0
        elif weight < 200:
            cost = 59.0
        elif weight < 300:
            cost = 71.0
        else:
            cost = 79.0

        return {"cost": cost, "currency": "BHD", "usd_cost": cost * bhd_to_usd}

    # No charge for domestic/international flights
    return {"cost": 0, "currency": "BHD", "usd_cost": 0}
