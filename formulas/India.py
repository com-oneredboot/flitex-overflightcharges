"""
India Overflight Charges Formula

Currency: INR (Indian Rupee)
Conversion: 1 INR = 0.012 USD

Rates:
- Weight limit: 200 tonnes (capped for calculation)
- Distance limit: 1200 NM (capped for calculation)
- Unit rate: 4620 INR
- Fixed overflight charge: 4400 INR

Logic:
- Domestic: weight_factor + distance_factor + landing_rate * 0.75
- International (destination India): weight_factor + distance_factor + landing_rate
- Overflight: weight_factor + distance_factor + fixed_overflight_charge

Factors:
- weight_factor = sqrt(min(weight, 200) / 50)
- distance_factor = sqrt(min(distance, 1200) / 100)
"""


def calculate(distance, weight, context):
    """
    Calculate India overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    inr_to_usd = 0.012
    weight_limit_tonnes = 200
    distance_limit_nm = 1200
    fixed_overflight_charge = 4400
    domestic_reduction_factor = 0.75

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Calculate factors with limits
    capped_weight = min(weight, weight_limit_tonnes)
    capped_distance = min(distance, distance_limit_nm)

    weight_factor = sqrt(capped_weight / 50)
    distance_factor = sqrt(capped_distance / 100)

    # Domestic flights
    if origin_country == "India" and destination_country == "India":
        rate_per_landing = (
            1087.90 * domestic_reduction_factor
            if weight < 10
            else 6546.10 * domestic_reduction_factor
        )
        cost = weight_factor + distance_factor + rate_per_landing
        return {"cost": cost, "currency": "INR", "usd_cost": cost * inr_to_usd}

    # International flights (destination is India)
    elif destination_country == "India":
        rate_per_landing = 1087.90 if weight < 10 else 6546.10
        cost = weight_factor + distance_factor + rate_per_landing
        return {"cost": cost, "currency": "INR", "usd_cost": cost * inr_to_usd}

    # Overflight
    else:
        cost = weight_factor + distance_factor + fixed_overflight_charge
        return {"cost": cost, "currency": "INR", "usd_cost": cost * inr_to_usd}
