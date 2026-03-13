"""
Cuba Overflight Charges Formula

Currency: CUC (Cuban Convertible Peso, 1:1 with USD)

Rates (weight-based flat charges):
- Route over Cuban territory (origin or destination FIR is Cuba):
  - Up to 15 tonnes: $74.62
  - 15-30 tonnes: $120.73
  - 30-70 tonnes: $153.53
  - 70-100 tonnes: $197.42
  - 100-200 tonnes: $252.26
  - Over 200 tonnes: $406.01

- Oceanic routes inside HAV FIR CTA (overflight):
  - Up to 15 tonnes: $62.17
  - 15-30 tonnes: $100.40
  - 30-70 tonnes: $127.99
  - 70-100 tonnes: $166.09
  - 100-200 tonnes: $210.20
  - Over 200 tonnes: $338.36
"""


def calculate(distance, weight, context):
    """
    Calculate Cuba overflight charges.

    Args:
        distance: Distance in nautical miles (not used in this formula)
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    origin_fir_tag = context.get("originFirTag")
    destination_fir_tag = context.get("destinationFirTag")
    fir_tag = context.get("firTag")

    # Determine if route is over Cuban territory or oceanic
    is_route_over = origin_fir_tag == fir_tag or destination_fir_tag == fir_tag

    if is_route_over:
        # Route over Cuban territory
        if weight <= 15:
            cost = 74.62
        elif weight <= 30:
            cost = 120.73
        elif weight <= 70:
            cost = 153.53
        elif weight <= 100:
            cost = 197.42
        elif weight <= 200:
            cost = 252.26
        else:
            cost = 406.01
    else:
        # Oceanic routes
        if weight <= 15:
            cost = 62.17
        elif weight <= 30:
            cost = 100.4
        elif weight <= 70:
            cost = 127.99
        elif weight <= 100:
            cost = 166.09
        elif weight <= 200:
            cost = 210.2
        else:
            cost = 338.36

    return {"cost": cost, "currency": "CUC", "usd_cost": cost}
