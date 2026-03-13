// US overflight charge formula
var distance_factor = distance_km / 100;
var weight_factor = mtow_kg / 1000;
var result = (distance_factor * weight_factor) * 25.50;
