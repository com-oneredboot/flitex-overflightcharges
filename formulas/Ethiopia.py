"""
Ethiopia Overflight Charges Formula

Currency: USD

Rates:
- Domestic: Weight-based flat rates (per flight)
  - Up to 5000 lbs: $2.49
  - 5000-50000 lbs: $10.78
  - 50000-120000 lbs: $35.90
  - 120000-300000 lbs: $93.32
  - Over 300000 lbs: $143.56

- International/Overflight: Weight and distance-based with NAFISAT charge
  - Under 10000 lbs: $7.51 + $10 NAFISAT
  - Over 10000 lbs: (rate * 16.24) + $10 NAFISAT
    - Rates vary by weight (50-Infinity tonnes) and distance (200-Infinity NM)

Note: Weight conversion 1 tonne = 2204.62 lbs
"""


def calculate(distance, weight, context):
    """
    Calculate Ethiopia overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    kg_to_lb = 2.20462
    unit_rate = 16.24
    nafisat_charge = 10

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    weight_lbs = weight * 1000 * kg_to_lb  # Convert tonnes to kg to lbs

    # Domestic flights
    if origin_country == "Ethiopia" and destination_country == "Ethiopia":
        if weight_lbs <= 5000:
            cost = 2.49
        elif weight_lbs <= 50000:
            cost = 10.78
        elif weight_lbs <= 120000:
            cost = 35.9
        elif weight_lbs <= 300000:
            cost = 93.32
        else:
            cost = 143.56

        return {"cost": cost, "currency": "USD", "usd_cost": cost}

    # International/Overflight
    else:
        if weight_lbs < 10000:
            cost = 7.51 + nafisat_charge
        else:
            # Determine rate based on weight and distance
            weight_tonnes = weight
            if weight_tonnes <= 50:
                if distance <= 200:
                    rate = 1
                elif distance <= 400:
                    rate = 2
                elif distance <= 1000:
                    rate = 3.5
                else:
                    rate = 5
            elif weight_tonnes <= 120:
                if distance <= 200:
                    rate = 2
                elif distance <= 400:
                    rate = 4
                elif distance <= 1000:
                    rate = 7
                else:
                    rate = 10
            elif weight_tonnes <= 300:
                if distance <= 200:
                    rate = 2.5
                elif distance <= 400:
                    rate = 5
                elif distance <= 1000:
                    rate = 8.75
                else:
                    rate = 12
            else:
                if distance <= 200:
                    rate = 3
                elif distance <= 400:
                    rate = 6
                elif distance <= 1000:
                    rate = 10.5
                else:
                    rate = 15

            cost = (rate * unit_rate) + nafisat_charge

        return {"cost": cost, "currency": "USD", "usd_cost": cost}
