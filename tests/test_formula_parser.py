"""Unit tests for FormulaParser.

Tests the formula parser's ability to parse Python formula strings
and validate their syntax.
"""

import ast
import pytest

from src.services.formula_parser import FormulaParser


class TestFormulaParser:
    """Test suite for FormulaParser class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = FormulaParser()
    
    def test_parse_simple_expression(self):
        """Test parsing a simple Python expression."""
        formula = "result = mtow_kg * 0.5"
        ast_module = self.parser.parse(formula)
        
        assert isinstance(ast_module, ast.Module)
        assert len(ast_module.body) > 0
    
    def test_parse_complex_formula(self):
        """Test parsing a complex formula with multiple operations."""
        formula = """
distance_factor = distance_km / 100
weight_factor = mtow_kg / 1000
result = (distance_factor * weight_factor) * 25.50
"""
        ast_module = self.parser.parse(formula)
        
        assert isinstance(ast_module, ast.Module)
        assert len(ast_module.body) == 3
    
    def test_parse_with_conditionals(self):
        """Test parsing formula with conditional logic."""
        formula = """
if mtow_kg > 50000:
    result = mtow_kg * 0.8
else:
    result = mtow_kg * 0.5
"""
        ast_module = self.parser.parse(formula)
        
        assert isinstance(ast_module, ast.Module)
        assert len(ast_module.body) > 0
    
    def test_parse_with_functions(self):
        """Test parsing formula with function calls."""
        formula = "result = max(mtow_kg * 0.5, 100)"
        ast_module = self.parser.parse(formula)
        
        assert isinstance(ast_module, ast.Module)
        assert len(ast_module.body) > 0
    
    def test_parse_invalid_syntax_raises_error(self):
        """Test that invalid syntax raises SyntaxError."""
        formula = "result = mtow_kg * 0.5 +"  # Incomplete expression
        
        with pytest.raises(SyntaxError):
            self.parser.parse(formula)
    
    def test_validate_syntax_valid_formula(self):
        """Test validate_syntax returns True for valid formula."""
        formula = "result = mtow_kg * distance_km * 0.01"
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_syntax_invalid_formula(self):
        """Test validate_syntax returns False with error message for invalid formula."""
        formula = "result = mtow_kg * 0.5 +"  # Incomplete expression
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is False
        assert error_msg is not None
        assert "Syntax error" in error_msg
    
    def test_validate_syntax_missing_colon(self):
        """Test validate_syntax detects missing colon in if statement."""
        formula = """
if mtow_kg > 50000
    result = mtow_kg * 0.8
"""
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is False
        assert error_msg is not None
        assert "line 2" in error_msg
    
    def test_validate_syntax_invalid_indentation(self):
        """Test validate_syntax detects invalid indentation."""
        formula = """
if mtow_kg > 50000:
result = mtow_kg * 0.8
"""
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is False
        assert error_msg is not None
    
    def test_validate_syntax_unclosed_parenthesis(self):
        """Test validate_syntax detects unclosed parenthesis."""
        formula = "result = (mtow_kg * 0.5"
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is False
        assert error_msg is not None
    
    def test_validate_syntax_empty_string(self):
        """Test validate_syntax handles empty string."""
        formula = ""
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        # Empty string is valid Python (empty module)
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_syntax_whitespace_only(self):
        """Test validate_syntax handles whitespace-only string."""
        formula = "   \n\n   "
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        # Whitespace-only is valid Python (empty module)
        assert is_valid is True
        assert error_msg is None
    
    def test_validate_syntax_error_includes_line_number(self):
        """Test that error message includes line number."""
        formula = """
result = mtow_kg * 0.5
invalid syntax here
"""
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is False
        assert error_msg is not None
        assert "line" in error_msg.lower()
    
    def test_parse_multiline_formula(self):
        """Test parsing multiline formula with comments."""
        formula = """
# Calculate base charge
base_charge = mtow_kg * 0.5

# Apply distance factor
distance_factor = distance_km / 100
result = base_charge * distance_factor
"""
        ast_module = self.parser.parse(formula)
        
        assert isinstance(ast_module, ast.Module)
        # Comments are not included in AST, so we should have 3 statements
        assert len(ast_module.body) == 3
    
    def test_validate_syntax_with_imports(self):
        """Test validate_syntax with import statements."""
        formula = """
import math
result = math.sqrt(mtow_kg) * distance_km
"""
        is_valid, error_msg = self.parser.validate_syntax(formula)
        
        assert is_valid is True
        assert error_msg is None
