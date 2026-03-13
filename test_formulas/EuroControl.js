// EuroControl regional overflight charge formula
// Applies to European airspace managed by EuroControl
var distance_factor = distance_km / 100;
var weight_factor = mtow_kg / 1000;
var eurocontrol_rate = 62.78;
var result = (distance_factor * weight_factor) * eurocontrol_rate;
