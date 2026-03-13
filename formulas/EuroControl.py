"""
EuroControl Overflight Charges Formula

Currency: Varies by country (EUR default)
Conversion: 1 EUR = 1.10 USD

Formula:
- Cost = unit_rate * distance_factor * weight_factor * exchange_rate
- distance_factor = distance / 100
- weight_factor = (weight / 50) ^ 0.7

Note: Unit rates are fetched from eurocontrol_rates pre-loaded data
Special case: LPPO FIR uses AZ country code
"""


def calculate(distance, weight, context):
    """
    Calculate EuroControl overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.
                 Must include eurocontrol_rates data

    Returns:
        Dictionary with cost, currency, usd_cost, and euroCost
    """
    fir_tag = context.get("firTag", "")
    eurocontrol_rates = context.get("eurocontrol_rates", {})

    # Special case for LPPO FIR
    if fir_tag == "LPPO":
        country_code = "AZ"
    else:
        country_code = fir_tag[:2] if len(fir_tag) >= 2 else ""

    # Get rate data for this country
    rate_data = eurocontrol_rates.get(country_code, {})

    unit_rate = rate_data.get("unit_rate", 0) / 100 if rate_data.get("unit_rate") else 0
    exchange_rate = rate_data.get("ex_rate_to_eur", 1)
    currency = rate_data.get("currency", "EUR")
    euro_to_usd_rate = 1.10

    # Calculate factors
    distance_factor = distance / 100
    weight_factor = pow(weight / 50, 0.7)

    # Calculate costs
    euro_cost = weight_factor * distance_factor * unit_rate
    cost = euro_cost * exchange_rate
    usd_cost = euro_cost * euro_to_usd_rate

    return {
        "cost": cost,
        "currency": currency,
        "euroCost": euro_cost,
        "usd_cost": usd_cost,
    }
