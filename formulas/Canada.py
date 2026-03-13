"""
Canada Overflight Charges Formula

Currency: CAD (Canadian Dollar)
Conversion: 1 CAD = 0.75 USD

Rates:
- North Atlantic (Oceanic FIRs): $230.22 CAD flat
- En-route: 0.03802 CAD per km * sqrt(weight)
- Terminal Service Charge: 31.86 * weight^0.8 (for departing flights only)

Special cases:
- USA to USA flights: $0
- Distance reduction for terminal airports (35 or 65 km)
"""


def calculate(distance, weight, context):
    """
    Calculate Canada overflight charges.

    Args:
        distance: Distance in nautical miles
        weight: Aircraft weight in tonnes
        context: Dictionary containing originCountry, destinationCountry, etc.

    Returns:
        Dictionary with cost, currency, and usd_cost
    """
    cad_to_usd = 0.75
    north_atlantic_fixed_rate = 230.22
    en_route_rate = 0.03802
    terminal_service_charge_rate = 31.86
    weight_factor = 0.8

    fir_name = context.get("firName", "")
    arrival = context.get("arrival")
    departure = context.get("departure")
    is_first_fir = context.get("isFirstFir", False)
    is_last_fir = context.get("isLastFir", False)
    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # Oceanic FIR
    if "OCEANIC" in fir_name.upper():
        return {
            "cost": north_atlantic_fixed_rate,
            "currency": "CAD",
            "usd_cost": north_atlantic_fixed_rate * cad_to_usd,
        }

    # USA to USA flights
    if origin_country == "USA" and destination_country == "USA":
        return {"cost": 0, "currency": "USD", "usd_cost": 0}

    # Find terminal airport and km reduction
    terminal_airport = None
    if is_first_fir and departure:
        terminal_airport = next(
            (a for a in CANADA_TSC_AERODROMES if a.get("icao") == departure), None
        )
    elif is_last_fir and arrival:
        terminal_airport = next(
            (a for a in CANADA_TSC_AERODROMES if a.get("icao") == arrival), None
        )

    km_reduction = 0
    if terminal_airport:
        reduction_info = terminal_airport.get("reduction", {})
        km_reduction = 65 if reduction_info.get("sixtyFiveKm") else 35

    # Terminal service charges (only for departing flights)
    is_departing_airport = terminal_airport and is_first_fir
    terminal_service_charges = (
        terminal_service_charge_rate * pow(weight, weight_factor)
        if is_departing_airport
        else 0
    )

    # En-route charges
    distance_km = distance  # Already in NM, formula uses as-is
    calculation_one = max(0, distance_km - km_reduction)
    calculation_two = sqrt(weight)
    calculated_cost = (
        en_route_rate * calculation_one * calculation_two
    ) + terminal_service_charges

    return {
        "cost": calculated_cost,
        "currency": "CAD",
        "usd_cost": calculated_cost * cad_to_usd,
    }
