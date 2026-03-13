"""
Afghanistan Overflight Charges Formula

Rates:
- Overflight: $700 USD
- Landing/Takeoff: $100 USD

Logic:
- If neither origin nor destination is Afghanistan: overflight rate
- Otherwise: landing rate
"""


def calculate(distance, weight, context):
    """
    Calculate Afghanistan overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes (not used in this formula)
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    overflight_rate = 700
    landing_rate = 100

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    if origin_country != "Afghanistan" and destination_country != "Afghanistan":
        return {"cost": overflight_rate, "currency": "USD", "usd_cost": overflight_rate}
    else:
        return {"cost": landing_rate, "currency": "USD", "usd_cost": landing_rate}
