"""
Guyana Overflight Charges Formula

Currency: GYD (domestic), USD (international)

Rates:
- Domestic (per hour based on weight in pounds):
  - Up to 7000 lbs: $150/hour
  - 7000-14000 lbs: $250/hour
  - Over 14000 lbs: $400/hour

- International: 11.5 * sqrt(weight), minimum $140
"""


def calculate(distance, weight, context):
    """
    Calculate Guyana overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, time, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Domestic flights
    if origin_country == "Guyana" and destination_country == "Guyana":
        weight_pounds = weight * 2204.62
        time_seconds = context.get("time", 0)
        hours = time_seconds / 3600

        if weight_pounds <= 7000:
            rate_per_hour = 150
        elif weight_pounds <= 14000:
            rate_per_hour = 250
        else:
            rate_per_hour = 400

        cost = rate_per_hour * hours
        return {"cost": cost, "currency": "GYD", "usd_cost": cost}

    # International flights
    else:
        unit_rate = 11.5
        min_cost = 140
        calculated_cost = unit_rate * sqrt(weight)
        cost = max(calculated_cost, min_cost)

        return {"cost": cost, "currency": "USD", "usd_cost": cost}
