"""
Ashgabat (Turkmenistan) Overflight Charges Formula

Currency: USD

Rates (weight-based):
- Up to 50 tonnes: $32
- Up to 100 tonnes: $44
- Up to 200 tonnes: $54
- Up to 300 tonnes: $56
- Up to 400 tonnes: $57
- Over 400 tonnes: $59

Additional:
- Origin surcharge: $50 EUR equivalent if origin is Ashgabat
"""


def calculate(distance, weight, context):
    """
    Calculate Ashgabat overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    eur_to_usd = 1.09

    origin_country = context.get("originCountry")

    # Determine base cost from weight tiers
    if weight <= 50:
        cost = 32
    elif weight <= 100:
        cost = 44
    elif weight <= 200:
        cost = 54
    elif weight <= 300:
        cost = 56
    elif weight <= 400:
        cost = 57
    else:
        cost = 59

    # Add origin surcharge if applicable
    if origin_country == "Ashgabat":
        cost += 50 / eur_to_usd

    return {"cost": cost, "currency": "USD", "usd_cost": cost / eur_to_usd}
