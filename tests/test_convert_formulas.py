"""
Unit tests for formula conversion script.

Tests JavaScript to Python syntax conversion, constant import replacement,
utility function replacement, and logic preservation.

Requirements: 7.3, 7.4, 7.5, 7.6
"""

import pytest
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from convert_formulas import (
    extract_country_code_from_filename,
    extract_description_from_filename,
    convert_javascript_to_python
)


class TestCountryCodeExtraction:
    """Test country code extraction from filenames."""
    
    def test_extract_country_code_from_two_letter_pattern(self):
        """Test extraction from XX_formula.js pattern."""
        assert extract_country_code_from_filename("US_formula.js") == "US"
        assert extract_country_code_from_filename("CA_formula.js") == "CA"
        assert extract_country_code_from_filename("GB_formula.js") == "GB"
    
    def test_extract_country_code_from_two_letter_simple(self):
        """Test extraction from XX.js pattern."""
        assert extract_country_code_from_filename("US.js") == "US"
        assert extract_country_code_from_filename("CA.js") == "CA"
        assert extract_country_code_from_filename("GB.js") == "GB"
    
    def test_extract_country_code_regional_formulas(self):
        """Test that regional formulas return None."""
        assert extract_country_code_from_filename("EuroControl.js") is None
        assert extract_country_code_from_filename("Oceanic.js") is None
    
    def test_extract_country_code_non_formula_files(self):
        """Test that non-formula files return None."""
        assert extract_country_code_from_filename("Template.js") is None
        assert extract_country_code_from_filename("TemplateLoop.js") is None
        assert extract_country_code_from_filename("FormulaMap.js") is None


class TestDescriptionExtraction:
    """Test description extraction from filenames."""
    
    def test_extract_description_regional_formulas(self):
        """Test description extraction for regional formulas."""
        assert extract_description_from_filename("EuroControl.js", None) == "EuroControl"
        assert extract_description_from_filename("Oceanic.js", None) == "Oceanic"
    
    def test_extract_description_country_formulas(self):
        """Test description extraction for country formulas."""
        assert extract_description_from_filename("US_formula.js", "US") == "US"
        assert extract_description_from_filename("CA.js", "CA") == "CA"
        assert extract_description_from_filename("GB.js", "GB") == "GB"


class TestJavaScriptToPythonConversion:
    """Test JavaScript to Python syntax conversion."""
    
    def test_convert_variable_declarations(self):
        """Test conversion of var/let/const to Python assignments (Requirement 7.4)."""
        js_code = """
        var distance_factor = distance_km / 100;
        let weight_factor = mtow_kg / 1000;
        const rate = 25.50;
        var result = (distance_factor * weight_factor) * rate;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        assert "var " not in python_code
        assert "let " not in python_code
        assert "const " not in python_code
        assert "distance_factor = " in python_code
        assert "weight_factor = " in python_code
        assert "rate = " in python_code
        # Check that parameter conversions are added
        assert "distance_km = convert_nm_to_km(distance)" in python_code
        assert "mtow_kg = weight * 1000" in python_code
    
    def test_convert_operators(self):
        """Test conversion of JavaScript operators to Python (Requirement 7.4)."""
        js_code = """
        var a = x === y;
        var b = x !== y;
        var c = x && y;
        var d = x || y;
        var result = a;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        assert "===" not in python_code
        assert "!==" not in python_code
        assert "&&" not in python_code
        assert "||" not in python_code
        assert " == " in python_code
        assert " != " in python_code
        assert " and " in python_code
        assert " or " in python_code
    
    def test_convert_math_functions(self):
        """Test conversion of Math functions to Python (Requirement 7.4)."""
        js_code = """
        var a = Math.floor(x);
        var b = Math.ceil(y);
        var c = Math.round(z);
        var d = Math.pow(x, 2);
        var e = Math.sqrt(x);
        var f = Math.abs(x);
        var result = a + b + c + d + e + f;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        assert "Math.floor" not in python_code
        assert "Math.ceil" not in python_code
        assert "Math.round" not in python_code
        assert "Math.pow" not in python_code
        assert "Math.sqrt" not in python_code
        assert "Math.abs" not in python_code
        assert "int(" in python_code
        assert "ceil(" in python_code
        assert "round(" in python_code
        assert "pow(" in python_code
        assert "sqrt(" in python_code
        assert "abs(" in python_code
    
    def test_replace_convert_nm_to_km(self):
        """Test replacement of convertNmToKm with convert_nm_to_km (Requirement 7.5)."""
        js_code = """
        var distance_km = convertNmToKm(distance_nm);
        var result = distance_km * 10;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        assert "convertNmToKm" not in python_code
        assert "convert_nm_to_km" in python_code
    
    def test_remove_semicolons(self):
        """Test removal of semicolons."""
        js_code = """
        var x = 10;
        var y = 20;
        var result = x + y;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        assert ";" not in python_code
    
    def test_wrap_in_calculate_function(self):
        """Test that code is wrapped in calculate function (Requirement 4.1)."""
        js_code = """
        var distance_factor = distance_km / 100;
        var result = distance_factor * 10;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        assert "def calculate(distance, weight, context):" in python_code
        # Check parameter conversions are added
        assert "distance_km = convert_nm_to_km(distance)" in python_code
        assert "mtow_kg = weight * 1000" in python_code
        assert "return {" in python_code
        assert '"cost": result' in python_code
        assert '"currency": "USD"' in python_code
        assert '"usd_cost": result' in python_code
    
    def test_preserve_formula_logic(self):
        """Test that formula logic is preserved during conversion (Requirement 7.3)."""
        js_code = """
        var distance_factor = distance_km / 100;
        var weight_factor = mtow_kg / 1000;
        var result = (distance_factor * weight_factor) * 25.50;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        # Check that the core logic is preserved
        assert "distance_factor = distance_km / 100" in python_code
        assert "weight_factor = mtow_kg / 1000" in python_code
        assert "result = (distance_factor * weight_factor) * 25.50" in python_code
    
    def test_convert_us_formula(self):
        """Test conversion of actual US formula."""
        js_code = """
        // US overflight charge formula
        var distance_factor = distance_km / 100;
        var weight_factor = mtow_kg / 1000;
        var result = (distance_factor * weight_factor) * 25.50;
        """
        
        python_code = convert_javascript_to_python(js_code, "US_formula.js")
        
        assert python_code is not None
        assert "def calculate(distance, weight, context):" in python_code
        assert "distance_factor = distance_km / 100" in python_code
        assert "weight_factor = mtow_kg / 1000" in python_code
        assert "result = (distance_factor * weight_factor) * 25.50" in python_code
        assert "return {" in python_code
    
    def test_convert_eurocontrol_formula(self):
        """Test conversion of actual EuroControl formula."""
        js_code = """
        // EuroControl regional overflight charge formula
        var distance_factor = distance_km / 100;
        var weight_factor = mtow_kg / 1000;
        var eurocontrol_rate = 62.78;
        var result = (distance_factor * weight_factor) * eurocontrol_rate;
        """
        
        python_code = convert_javascript_to_python(js_code, "EuroControl.js")
        
        assert python_code is not None
        assert "def calculate(distance, weight, context):" in python_code
        assert "distance_factor = distance_km / 100" in python_code
        assert "weight_factor = mtow_kg / 1000" in python_code
        assert "eurocontrol_rate = 62.78" in python_code
        assert "result = (distance_factor * weight_factor) * eurocontrol_rate" in python_code
        assert "return {" in python_code
    
    def test_handle_comments(self):
        """Test that comments are removed during conversion."""
        js_code = """
        // This is a comment
        var x = 10; // inline comment
        /* Multi-line
           comment */
        var result = x * 2;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        # Comments should be removed (except the docstring)
        assert "//" not in python_code
        assert "/*" not in python_code
        assert "*/" not in python_code
    
    def test_handle_empty_code(self):
        """Test handling of empty JavaScript code."""
        js_code = ""
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        # Should still create a valid calculate function
        assert python_code is not None
        assert "def calculate(distance, weight, context):" in python_code
    
    def test_handle_invalid_code(self):
        """Test handling of invalid JavaScript code."""
        js_code = "this is not valid javascript @#$%"
        
        # Should not crash, may return None or attempt conversion
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        # As long as it doesn't crash, we're good
        assert python_code is None or isinstance(python_code, str)


class TestConstantImportReplacement:
    """Test replacement of JavaScript constant imports (Requirement 7.6)."""
    
    def test_no_import_statements_in_output(self):
        """Test that converted code has no import statements."""
        js_code = """
        var distance_factor = distance_km / 100;
        var result = distance_factor * 10;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        # Converted code should not have import statements
        # (constants are pre-loaded in execution context)
        assert "import " not in python_code
        assert "from " not in python_code
    
    def test_direct_constant_references(self):
        """Test that constants can be referenced directly (Requirement 7.6)."""
        js_code = """
        var currency = CURRENCY_CONSTANTS.USD;
        var country = COUNTRY_NAME_CONSTANTS.USA;
        var result = 100;
        """
        
        python_code = convert_javascript_to_python(js_code, "test.js")
        
        assert python_code is not None
        # Constants should be referenced directly (they're in execution context)
        assert "CURRENCY_CONSTANTS" in python_code or "currency = " in python_code
        assert "COUNTRY_NAME_CONSTANTS" in python_code or "country = " in python_code
