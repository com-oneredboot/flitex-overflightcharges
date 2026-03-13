"""Formula parser for Python AST parsing and validation.

This module provides the FormulaParser class for parsing Python formula strings
into abstract syntax trees and validating their syntax.
"""

import ast
from typing import Optional, Tuple


class FormulaParser:
    """Parser for Python formula strings.
    
    This class provides methods to parse Python formula strings into AST
    (Abstract Syntax Tree) representations and validate their syntax.
    """
    
    def parse(self, formula_string: str) -> ast.Module:
        """Parse Python formula string into AST.
        
        Args:
            formula_string: Python code as string
        
        Returns:
            Python AST Module
        
        Raises:
            SyntaxError: If formula has invalid Python syntax
        """
        return ast.parse(formula_string, mode='exec')
    
    def validate_syntax(self, formula_string: str) -> Tuple[bool, Optional[str]]:
        """Validate Python syntax without executing.
        
        Args:
            formula_string: Python code as string
        
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if syntax is valid, False otherwise
            - error_message: None if valid, descriptive error message if invalid
        """
        try:
            self.parse(formula_string)
            return (True, None)
        except SyntaxError as e:
            # Build descriptive error message
            error_msg = f"Syntax error at line {e.lineno}"
            if e.offset:
                error_msg += f", column {e.offset}"
            if e.msg:
                error_msg += f": {e.msg}"
            if e.text:
                error_msg += f"\n  {e.text.strip()}"
                if e.offset:
                    error_msg += f"\n  {' ' * (e.offset - 1)}^"
            return (False, error_msg)
        except Exception as e:
            # Catch any other parsing errors
            return (False, f"Parsing error: {str(e)}")
