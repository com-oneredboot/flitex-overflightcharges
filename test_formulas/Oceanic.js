// Oceanic regional overflight charge formula
// Applies to oceanic airspace regions
var distance_factor = distance_km / 100;
var weight_factor = mtow_kg / 1000;
var oceanic_rate = 48.50;
var result = (distance_factor * weight_factor) * oceanic_rate;
