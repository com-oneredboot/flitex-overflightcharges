"""
Cape Verde Overflight Charges Formula

Currency: CVE (domestic/international), EUR (overflight)
Conversion: 1 CVE = 0.0099 USD, 1 EUR = 1.09 USD

Rates:
- Terminal/Navaid (origin or destination Cape Verde): Weight-based flat rates in CVE
- Overflight: Distance and weight-based rates in EUR

Terminal rates (CVE):
- Up to 10 tonnes: 2500
- 10-25 tonnes: 3500
- 25-129 tonnes: 12500
- Over 129 tonnes: 25000

Overflight rates (EUR unit rate 20.86 * multiplier):
- Distance <= 700 NM: multipliers 3-25 based on weight
- 700 < distance <= 1000 NM: multipliers 6-50 based on weight
- Distance > 1000 NM: multipliers 12-100 based on weight
"""


def calculate(distance, weight, context):
    """
    Calculate Cape Verde overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    cve_to_usd = 0.0099
    eur_to_usd = 1.09
    eur_unit_rate = 20.86

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Terminal/Navaid charges (origin or destination is Cape Verde)
    if origin_country == "Cape Verde" or destination_country == "Cape Verde":
        if weight <= 10:
            cost = 2500.00
        elif weight <= 25:
            cost = 3500.00
        elif weight <= 129:
            cost = 12500.00
        else:
            cost = 25000.00

        return {"cost": cost, "currency": "CVE", "usd_cost": cost * cve_to_usd}

    # Overflight charges
    else:
        # Determine multiplier based on distance and weight
        if distance <= 700:
            if weight <= 139:
                multiplier = 3
            elif weight <= 199:
                multiplier = 10
            elif weight <= 269:
                multiplier = 14
            elif weight <= 349:
                multiplier = 18
            elif weight <= 439:
                multiplier = 22
            else:
                multiplier = 25
        elif distance <= 1000:
            if weight <= 139:
                multiplier = 6
            elif weight <= 199:
                multiplier = 20
            elif weight <= 269:
                multiplier = 28
            elif weight <= 349:
                multiplier = 36
            elif weight <= 439:
                multiplier = 44
            else:
                multiplier = 50
        else:  # distance > 1000
            if weight <= 139:
                multiplier = 12
            elif weight <= 199:
                multiplier = 40
            elif weight <= 269:
                multiplier = 56
            elif weight <= 349:
                multiplier = 72
            elif weight <= 439:
                multiplier = 88
            else:
                multiplier = 100

        cost = eur_unit_rate * multiplier
        return {"cost": cost, "currency": "EUR", "usd_cost": cost * eur_to_usd}
