"""Formula pretty printer for AST formatting.

This module provides the FormulaPrettyPrinter class for converting Python AST
(Abstract Syntax Tree) back to formatted Python code strings.
"""

import ast


class FormulaPrettyPrinter:
    """Pretty printer for Python formula AST.
    
    This class provides methods to convert Python AST representations back
    into formatted Python code strings. It works in conjunction with
    FormulaParser to enable round-trip parsing and formatting of formulas.
    """
    
    def print_ast(self, ast_node: ast.Module) -> str:
        """Convert Python AST back to formatted string.
        
        Uses ast.unparse() available in Python 3.9+ to convert an AST node
        back into Python source code. This enables round-trip parsing:
        parse -> AST -> print -> parse should produce equivalent AST.
        
        Args:
            ast_node: Python AST Module
        
        Returns:
            Formatted Python code string
        
        Raises:
            TypeError: If ast_node is not a valid AST node
        """
        if not isinstance(ast_node, ast.AST):
            raise TypeError(f"Expected ast.AST node, got {type(ast_node).__name__}")
        
        return ast.unparse(ast_node)
