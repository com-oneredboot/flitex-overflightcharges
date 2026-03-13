"""
Chile Overflight Charges Formula

Currency: CLP (Chilean Peso) for domestic, USD for international/overflight
Conversion: 1 CLP = 0.0012 USD

Rates:
- International (USD per km, with minimum):
  - Up to 10 tonnes: 0.062, min 16.85
  - 10-50 tonnes: 0.094, min 45.50
  - Over 50 tonnes: 0.114, min 91.35

- Domestic (CLP per km, with minimum):
  - Up to 10 tonnes: 3.70, min 1293
  - Over 10 tonnes: 20.11, min 6940

- ILS Terminal Navaid (CLP, added to calculated rate):
  - Up to 10 tonnes: 20384
  - 10-60 tonnes: 39387
  - Over 60 tonnes: 55177
"""


def calculate(distance, weight, context):
    """
    Calculate Chile overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    clp_to_usd = 0.0012

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    cost = 0

    # Domestic flights
    if origin_country == "Chile" and destination_country == "Chile":
        # Domestic rate
        if weight <= 10:
            rate, minimum = 3.70, 1293
        else:
            rate, minimum = 20.11, 6940

        temp = distance * rate
        cost += temp if temp >= minimum else minimum

        # ILS Terminal Navaid
        if weight < 10:
            cost += 20384
        elif weight < 60:
            cost += 39387
        else:
            cost += 55177

        return {"cost": cost, "currency": "CLP", "usd_cost": cost * clp_to_usd}

    # International flights (one endpoint is Chile)
    elif origin_country == "Chile" or destination_country == "Chile":
        # International rate (USD)
        if weight <= 10:
            rate, minimum = 0.062, 16.85
        elif weight <= 50:
            rate, minimum = 0.094, 45.50
        else:
            rate, minimum = 0.114, 91.35

        temp = distance * rate
        cost += temp if temp >= minimum else minimum

        # ILS Terminal Navaid (CLP)
        if weight < 10:
            cost += 20384
        elif weight < 60:
            cost += 39387
        else:
            cost += 55177

        return {"cost": cost, "currency": "CLP", "usd_cost": cost * clp_to_usd}

    # Overflights (neither endpoint is Chile)
    else:
        # International rate (USD)
        if weight <= 10:
            rate, minimum = 0.062, 16.85
        elif weight <= 50:
            rate, minimum = 0.094, 45.50
        else:
            rate, minimum = 0.114, 91.35

        temp = distance * rate
        cost += temp if temp >= minimum else minimum

        return {"cost": cost, "currency": "CLP", "usd_cost": cost * clp_to_usd}
