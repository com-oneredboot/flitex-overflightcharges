"""
Utility Functions for Formula Calculations

Common utility functions used in overflight charge formulas.
Converted from JavaScript @turf/helpers utilities.

Requirements: 3.6
"""


def convert_nm_to_km(nautical_miles: float) -> float:
    """
    Convert nautical miles to kilometers.

    Args:
        nautical_miles: Distance in nautical miles

    Returns:
        Distance in kilometers (nautical_miles * 1.852)

    Examples:
        >>> convert_nm_to_km(100)
        185.2
        >>> convert_nm_to_km(1)
        1.852
    """
    return nautical_miles * 1.852
