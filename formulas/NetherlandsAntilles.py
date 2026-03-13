"""
Netherlands Antilles Overflight Charges Formula

Currency: ANG (Netherlands Antillean Guilder)
Conversion: 1 ANG = 0.56 USD

Rates (weight-based with distance factor):
- Service units = weight_factor * ((distance - km_deduction) / 100)
- Cost = service_units * rate

Weight factors and rates vary by weight tier (2-Infinity tonnes)
"""


def calculate(distance, weight, context):
    """Calculate Netherlands Antilles overflight charges."""
    ang_to_usd = 0.56

    origin_country = context.get("originCountry")
    destination_country = context.get("destinationCountry")

    # 20 km deduction if Aruba is origin or destination
    km_deduction = 20 if origin_country == "Aruba" or destination_country == "Aruba" else 0
    km_distance_factor = (distance - km_deduction) / 100

    # Determine weight factor and rate
    if weight < 2:
        average_weight_factor, rate = 0.14, 6.59
    elif weight < 5.7:
        average_weight_factor, rate = 0.26, 12.24
    elif weight < 25:
        average_weight_factor, rate = 0.55, 25.89
    elif weight < 50:
        average_weight_factor, rate = 0.87, 40.96
    elif weight < 100:
        average_weight_factor, rate = 1.22, 57.44
    elif weight < 150:
        average_weight_factor, rate = 1.58, 74.39
    elif weight < 250:
        average_weight_factor, rate = 2.00, 94.16
    else:
        average_weight_factor, rate = 2.45, 115.35

    number_of_service_units = average_weight_factor * km_distance_factor
    calculated_cost = number_of_service_units * rate

    return {
        "cost": calculated_cost,
        "currency": "ANG",
        "usd_cost": calculated_cost * ang_to_usd,
    }
