"""
Bermuda Overflight Charges Formula

Currency: USD

Rates:
- En-route (origin or destination is Bermuda): $61.75 per 100 NM
- Oceanic (overflight): $26.51 per 100 NM

Formula:
- Cost = rate * (distance / 100)
"""


def calculate(distance, weight, context):
    """
    Calculate Bermuda overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    en_route_rate = 61.75
    oceanic_rate = 26.51

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Determine rate based on whether Bermuda is origin or destination
    if origin_country == "Bermuda" or destination_country == "Bermuda":
        rate = en_route_rate
    else:
        rate = oceanic_rate

    distance_per_100nm = distance / 100
    calculated_cost = rate * distance_per_100nm

    return {"cost": calculated_cost, "currency": "USD", "usd_cost": calculated_cost}
