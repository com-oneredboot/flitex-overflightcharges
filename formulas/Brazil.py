"""
Brazil Overflight Charges Formula

Currency: BRL (domestic), USD (international/overflight)
Conversion: 1 BRL = 0.20 USD

Rates vary by FIR and flight type:
- High-rate FIRs (SBCT, SBPV, SBBS, SBEG, SBBE, SBRF):
  - Domestic: 0.72 BRL
  - International/Overflight: 0.6 USD
- Other FIRs:
  - Domestic: 0.39 BRL
  - International/Overflight: 0.13 USD

Formula:
- Cost = unit_rate * (distance/100) * sqrt(weight/50)
"""


def calculate(distance, weight, context):
    """
    Calculate Brazil overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    fir_tag = context.get("firTag")
    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    high_rate_firs = ["SBCT", "SBPV", "SBBS", "SBEG", "SBBE", "SBRF"]

    # Domestic flights
    if origin_country == "Brazil" and destination_country == "Brazil":
        if fir_tag in high_rate_firs:
            unit_rate = 0.72
        else:
            unit_rate = 0.39

        cost = unit_rate * (distance / 100) * sqrt(weight / 50)
        return {"cost": cost, "currency": "BRL", "usd_cost": cost * 0.20}

    # International/Overflight
    else:
        if fir_tag in high_rate_firs:
            unit_rate = 0.6
        else:
            unit_rate = 0.13

        cost = unit_rate * (distance / 100) * sqrt(weight / 50)
        return {"cost": cost, "currency": "USD", "usd_cost": cost}
