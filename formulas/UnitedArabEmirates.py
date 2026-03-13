"""United Arab Emirates Overflight Charges Formula"""


def calculate(distance, weight, context):
    origin = context.get("originCountry")
    dest = context.get("destinationCountry")
    
    if origin == "United Arab Emirates" or dest == "United Arab Emirates":
        if weight < 120:
            cost = 60.00
        elif weight < 190:
            cost = 75.00
        elif weight < 290:
            cost = 90.00
        else:
            cost = 105.00
    else:
        if weight < 120:
            cost = 130.00
        elif weight < 190:
            cost = 165.00
        elif weight < 290:
            cost = 200.00
        else:
            cost = 235.00
    
    return {"cost": cost, "currency": "USD", "usd_cost": cost}
