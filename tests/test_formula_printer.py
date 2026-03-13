"""Unit tests for FormulaPrettyPrinter.

Tests the formula pretty printer's ability to convert Python AST back to
formatted code strings.
"""

import ast
import pytest

from src.services.formula_parser import FormulaParser
from src.services.formula_printer import FormulaPrettyPrinter


class TestFormulaPrettyPrinter:
    """Test suite for FormulaPrettyPrinter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.printer = FormulaPrettyPrinter()
        self.parser = FormulaParser()
    
    def test_print_simple_expression(self):
        """Test printing a simple Python expression."""
        formula = "result = mtow_kg * 0.5"
        ast_module = self.parser.parse(formula)
        
        printed = self.printer.print_ast(ast_module)
        
        assert isinstance(printed, str)
        assert "result" in printed
        assert "mtow_kg" in printed
        assert "0.5" in printed
    
    def test_print_complex_formula(self):
        """Test printing a complex formula with multiple operations."""
        formula = """distance_factor = distance_km / 100
weight_factor = mtow_kg / 1000
result = distance_factor * weight_factor * 25.5"""
        ast_module = self.parser.parse(formula)
        
        printed = self.printer.print_ast(ast_module)
        
        assert isinstance(printed, str)
        assert "distance_factor" in printed
        assert "weight_factor" in printed
        assert "result" in printed
    
    def test_print_with_conditionals(self):
        """Test printing formula with conditional logic."""
        formula = """if mtow_kg > 50000:
    result = mtow_kg * 0.8
else:
    result = mtow_kg * 0.5"""
        ast_module = self.parser.parse(formula)
        
        printed = self.printer.print_ast(ast_module)
        
        assert isinstance(printed, str)
        assert "if" in printed
        assert "else" in printed
        assert "mtow_kg > 50000" in printed
    
    def test_print_with_functions(self):
        """Test printing formula with function calls."""
        formula = "result = max(mtow_kg * 0.5, 100)"
        ast_module = self.parser.parse(formula)
        
        printed = self.printer.print_ast(ast_module)
        
        assert isinstance(printed, str)
        assert "max" in printed
        assert "mtow_kg" in printed
        assert "100" in printed
    
    def test_print_ast_invalid_input_raises_error(self):
        """Test that invalid input raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            self.printer.print_ast("not an ast node")
        
        assert "Expected ast.AST node" in str(exc_info.value)
    
    def test_print_ast_none_raises_error(self):
        """Test that None input raises TypeError."""
        with pytest.raises(TypeError):
            self.printer.print_ast(None)
    
    def test_roundtrip_simple_expression(self):
        """Test that parse -> print -> parse produces equivalent AST."""
        original = "result = mtow_kg * 0.5"
        
        # Parse original
        ast1 = self.parser.parse(original)
        
        # Print to string
        printed = self.printer.print_ast(ast1)
        
        # Parse printed version
        ast2 = self.parser.parse(printed)
        
        # Compare AST dumps (structural equivalence)
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_roundtrip_complex_formula(self):
        """Test roundtrip with complex formula."""
        original = """distance_factor = distance_km / 100
weight_factor = mtow_kg / 1000
result = distance_factor * weight_factor * 25.5"""
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_roundtrip_with_conditionals(self):
        """Test roundtrip with conditional logic."""
        original = """if mtow_kg > 50000:
    result = mtow_kg * 0.8
else:
    result = mtow_kg * 0.5"""
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_roundtrip_with_functions(self):
        """Test roundtrip with function calls."""
        original = "result = max(mtow_kg * 0.5, 100)"
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_roundtrip_multiline_formula(self):
        """Test roundtrip with multiline formula (comments are lost)."""
        # Note: Comments are not preserved in AST
        original = """base_charge = mtow_kg * 0.5
distance_factor = distance_km / 100
result = base_charge * distance_factor"""
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_roundtrip_with_imports(self):
        """Test roundtrip with import statements."""
        original = """import math
result = math.sqrt(mtow_kg) * distance_km"""
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_print_empty_module(self):
        """Test printing an empty AST module."""
        ast_module = ast.Module(body=[], type_ignores=[])
        
        printed = self.printer.print_ast(ast_module)
        
        assert isinstance(printed, str)
        # Empty module should produce empty or whitespace-only string
        assert printed.strip() == ""
    
    def test_print_preserves_operator_precedence(self):
        """Test that operator precedence is preserved in printed output."""
        original = "result = mtow_kg * distance_km + 100"
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        # Verify structural equivalence
        assert ast.dump(ast1) == ast.dump(ast2)
        
        # Verify the printed version is valid and parseable
        is_valid, error_msg = self.parser.validate_syntax(printed)
        assert is_valid is True
        assert error_msg is None
    
    def test_print_nested_expressions(self):
        """Test printing nested expressions."""
        original = "result = ((mtow_kg * 0.5) + (distance_km * 0.1)) / 100"
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
    
    def test_print_with_multiple_statements(self):
        """Test printing multiple statements."""
        original = """a = 1
b = 2
c = a + b
result = c * mtow_kg"""
        
        ast1 = self.parser.parse(original)
        printed = self.printer.print_ast(ast1)
        ast2 = self.parser.parse(printed)
        
        assert ast.dump(ast1) == ast.dump(ast2)
