"""Property-based tests for FormulaExecutor.

These tests verify universal properties across many generated inputs using Hypothesis.
Each property test runs with a minimum of 100 iterations.

Feature: python-formula-execution-system
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from unittest.mock import Mock
from uuid import uuid4

from src.formula_execution.formula_executor import FormulaExecutor
from src.formula_execution.formula_cache import FormulaCache
from src.formula_execution.constants_provider import ConstantsProvider
from src.formula_execution.eurocontrol_loader import EuroControlRateLoader
from src.models.formula import Formula
from src.exceptions import InvalidSyntaxException, ServiceException


# Strategy for generating valid distances
distance_strategy = st.floats(
    min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating valid weights
weight_strategy = st.floats(
    min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False
)

# Strategy for generating context dictionaries
context_strategy = st.fixed_dictionaries(
    {
        "firTag": st.text(min_size=4, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "arrival": st.text(min_size=4, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "departure": st.text(min_size=4, max_size=4, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "isFirstFir": st.booleans(),
        "isLastFir": st.booleans(),
        "firName": st.text(min_size=1, max_size=50),
        "originCountry": st.text(min_size=2, max_size=2, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
        "destinationCountry": st.text(min_size=2, max_size=2, alphabet=st.characters(min_codepoint=65, max_codepoint=90)),
    }
)


def create_mock_redis() -> Mock:
    """Create a mock Redis client that simulates real Redis behavior."""
    redis_mock = Mock()
    storage = {}

    def mock_get(key):
        return storage.get(key)

    def mock_setex(key, ttl, value):
        storage[key] = value

    def mock_delete(key):
        if key in storage:
            del storage[key]

    def mock_scan_iter(match):
        pattern = match.replace("*", "")
        return [k for k in storage.keys() if k.startswith(pattern)]

    redis_mock.get = mock_get
    redis_mock.setex = mock_setex
    redis_mock.delete = mock_delete
    redis_mock.scan_iter = mock_scan_iter
    redis_mock._storage = storage

    return redis_mock


def create_test_formula(formula_logic: str, formula_id=None) -> Formula:
    """Create a test formula with given logic."""
    if formula_id is None:
        formula_id = uuid4()

    return Formula(
        id=formula_id,
        country_code="TEST",
        description="Test Formula",
        formula_code="TEST_FORMULA",
        formula_logic=formula_logic,
        effective_date="2024-01-01",
        currency="USD",
        version_number=1,
        is_active=True,
        created_by="test@example.com",
    )


def create_executor(mock_db_session=None):
    """Create a FormulaExecutor instance with fresh mocks."""
    if mock_db_session is None:
        mock_db_session = Mock()

    mock_redis = create_mock_redis()
    cache = FormulaCache(redis_client=mock_redis)
    constants_provider = ConstantsProvider()

    mock_rate_loader = Mock(spec=EuroControlRateLoader)
    mock_rate_loader.get_rates.return_value = {}

    return FormulaExecutor(
        db_session=mock_db_session,
        cache=cache,
        constants_provider=constants_provider,
        rate_loader=mock_rate_loader,
        timeout_seconds=1.0,
    )


def mock_db_for_formula(formula):
    """Create a mock db session that returns the given formula."""
    mock_db_session = Mock()
    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = formula
    mock_db_session.query.return_value = mock_query
    return mock_db_session


def mock_db_for_formulas(formulas_list):
    """Create a mock db session that returns formulas by ID lookup."""
    mock_db_session = Mock()

    def mock_query_side_effect(*args):
        mock_query = Mock()

        def filter_side_effect(*filter_args):
            mock_result = Mock()
            for f in formulas_list:
                if hasattr(filter_args[0], "right") and filter_args[0].right.value == f.id:
                    mock_result.first.return_value = f
                    return mock_result
            mock_result.first.return_value = None
            return mock_result

        mock_query.filter.side_effect = filter_side_effect
        return mock_query

    mock_db_session.query.side_effect = mock_query_side_effect
    return mock_db_session


class TestSandboxRestrictionEnforcement:
    """Property 1: Sandbox Restriction Enforcement tests."""

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_1_import_statement_blocked(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 9.3**

        Property 1: Sandbox Restriction Enforcement (Import Statements)

        For any formula code containing import statements, the Formula Executor
        should block execution and return a security violation error.
        
        Note: RestrictedPython compiles import statements successfully but they
        fail at execution time when the import is attempted.
        """
        formula_logic = """
import os
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        # Import statements compile but fail at execution
        with pytest.raises((ServiceException, ImportError, NameError)):
            executor.execute_formula(
                formula_id=formula.id,
                distance=distance,
                weight=weight,
                context=context,
            )

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_1_dangerous_builtins_blocked(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.6, 9.3**

        Property 1: Sandbox Restriction Enforcement (Dangerous Built-ins)

        For any formula code attempting to use dangerous built-ins (eval, exec,
        open, __import__), the Formula Executor should block execution.
        """
        dangerous_operations = [
            "eval('1+1')",
            "exec('x=1')",
            "open('/etc/passwd')",
            "__import__('os')",
        ]

        for operation in dangerous_operations:
            formula_logic = f"""
def calculate(distance, weight, context):
    result = {operation}
    return {{'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}}
"""
            formula = create_test_formula(formula_logic)
            mock_db_session = mock_db_for_formula(formula)
            executor = create_executor(mock_db_session)

            with pytest.raises((InvalidSyntaxException, ServiceException, NameError)):
                executor.execute_formula(
                    formula_id=formula.id,
                    distance=distance,
                    weight=weight,
                    context=context,
                )


class TestCalculateFunctionRequirement:
    """Property 4: Calculate Function Requirement tests."""

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_4_missing_calculate_function(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 4.1, 11.2**

        Property 4: Calculate Function Requirement

        For any formula submitted for validation or execution, if it does not
        define a calculate function with signature (distance, weight, context),
        the system should reject it with an appropriate error.
        """
        formula_logic = """
x = 10
y = 20
result = x + y
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        with pytest.raises(ServiceException) as exc_info:
            executor.execute_formula(
                formula_id=formula.id,
                distance=distance,
                weight=weight,
                context=context,
            )

        assert "calculate" in str(exc_info.value).lower()

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_4_wrong_function_name(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 4.1, 11.2**

        Property 4: Calculate Function Requirement (Wrong Name)

        For any formula with a function that is not named 'calculate',
        the system should reject it.
        """
        formula_logic = """
def compute(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        with pytest.raises(ServiceException) as exc_info:
            executor.execute_formula(
                formula_id=formula.id,
                distance=distance,
                weight=weight,
                context=context,
            )

        assert "calculate" in str(exc_info.value).lower()


class TestParameterPassingIntegrity:
    """Property 5: Parameter Passing Integrity tests."""

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_5_parameter_passing_integrity(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 4.2, 4.3, 4.4, 8.3**

        Property 5: Parameter Passing Integrity

        For any formula execution with given distance, weight, and context
        parameters, the formula should receive exactly those values without
        modification or loss of data.
        """
        formula_logic = """
def calculate(distance, weight, context):
    return {
        'cost': 0,
        'currency': 'USD',
        'usd_cost': 0,
        'received_distance': distance,
        'received_weight': weight,
        'received_context': context
    }
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        result = executor.execute_formula(
            formula_id=formula.id,
            distance=distance,
            weight=weight,
            context=context,
        )

        assert result["received_distance"] == distance
        assert result["received_weight"] == weight
        assert result["received_context"] == context

        for key, value in context.items():
            assert key in result["received_context"]
            assert result["received_context"][key] == value


class TestRequiredReturnFields:
    """Property 6: Required Return Fields tests."""

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
        cost=st.floats(
            min_value=0.0, max_value=100000.0, allow_nan=False, allow_infinity=False
        ),
    )
    def test_property_6_required_return_fields(
        self,
        distance: float,
        weight: float,
        context: dict,
        cost: float,
    ) -> None:
        """
        **Validates: Requirements 4.5**

        Property 6: Required Return Fields

        For any successful formula execution, the returned dictionary should
        contain the required fields: cost (float), currency (string), and
        usd_cost (float).
        """
        formula_logic = f"""
def calculate(distance, weight, context):
    return {{
        'cost': {cost},
        'currency': 'USD',
        'usd_cost': {cost}
    }}
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        result = executor.execute_formula(
            formula_id=formula.id,
            distance=distance,
            weight=weight,
            context=context,
        )

        assert "cost" in result
        assert "currency" in result
        assert "usd_cost" in result
        assert isinstance(result["cost"], (int, float))
        assert isinstance(result["currency"], str)
        assert isinstance(result["usd_cost"], (int, float))

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_6_missing_required_fields(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 4.5**

        Property 6: Required Return Fields (Missing Fields)

        For any formula that returns a dictionary missing required fields,
        the system should raise an error.
        """
        formula_logic = """
def calculate(distance, weight, context):
    return {'cost': 100.0}
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        with pytest.raises(ServiceException) as exc_info:
            executor.execute_formula(
                formula_id=formula.id,
                distance=distance,
                weight=weight,
                context=context,
            )

        error_msg = str(exc_info.value).lower()
        assert "missing" in error_msg or "required" in error_msg


class TestBatchExecutionCompleteness:
    """Property 9: Batch Execution Completeness tests."""

    @settings(max_examples=100, deadline=None)
    @given(
        batch_size=st.integers(min_value=1, max_value=10),
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_9_batch_execution_completeness(
        self,
        batch_size: int,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 5.5**

        Property 9: Batch Execution Completeness

        For any batch of formula execution requests, the batch execution should
        return a result (success or error) for each request in the same order.
        """
        formulas = []
        for i in range(batch_size):
            formula_logic = f"""
def calculate(distance, weight, context):
    return {{
        'cost': {i * 100.0},
        'currency': 'USD',
        'usd_cost': {i * 100.0},
        'index': {i}
    }}
"""
            formula = create_test_formula(formula_logic, formula_id=uuid4())
            formulas.append(formula)

        mock_db_session = mock_db_for_formulas(formulas)
        executor = create_executor(mock_db_session)

        executions = [
            {
                "formula_id": formula.id,
                "distance": distance,
                "weight": weight,
                "context": context,
            }
            for formula in formulas
        ]

        results = executor.execute_batch(executions)

        assert len(results) == batch_size
        for i, result in enumerate(results):
            assert "success" in result
            if result["success"]:
                assert result["result"]["index"] == i
            assert "formula_id" in result

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_9_batch_execution_partial_failure(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 5.5**

        Property 9: Batch Execution Completeness (Partial Failure)

        For any batch where some formulas fail, the batch execution should
        continue processing remaining formulas and return results for all.
        """
        valid_formula = create_test_formula(
            """
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
""",
            formula_id=uuid4(),
        )

        invalid_formula = create_test_formula(
            """
def calculate(distance, weight, context):
    return {'cost': 100.0}
""",
            formula_id=uuid4(),
        )

        mock_db_session = mock_db_for_formulas([valid_formula, invalid_formula])
        executor = create_executor(mock_db_session)

        executions = [
            {
                "formula_id": valid_formula.id,
                "distance": distance,
                "weight": weight,
                "context": context,
            },
            {
                "formula_id": invalid_formula.id,
                "distance": distance,
                "weight": weight,
                "context": context,
            },
            {
                "formula_id": valid_formula.id,
                "distance": distance,
                "weight": weight,
                "context": context,
            },
        ]

        results = executor.execute_batch(executions)

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "error" in results[1]
        assert results[2]["success"] is True


class TestDatabaseQueryPrevention:
    """Property 14: Database Query Prevention tests."""

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_14_database_query_prevention(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 2.3, 10.5**

        Property 14: Database Query Prevention

        For any formula execution, the formula code should not be able to make
        direct database queries; all data must come from the pre-loaded
        execution context.
        
        Note: Import statements compile but fail at execution time.
        """
        formula_logic = """
import sqlalchemy
def calculate(distance, weight, context):
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0}
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        # Import statements fail at execution time
        with pytest.raises((ServiceException, ImportError, NameError)):
            executor.execute_formula(
                formula_id=formula.id,
                distance=distance,
                weight=weight,
                context=context,
            )

    @settings(max_examples=100, deadline=None)
    @given(
        distance=distance_strategy,
        weight=weight_strategy,
        context=context_strategy,
    )
    def test_property_14_no_file_system_access(
        self,
        distance: float,
        weight: float,
        context: dict,
    ) -> None:
        """
        **Validates: Requirements 2.3, 10.5**

        Property 14: Database Query Prevention (File System)

        For any formula execution, the formula code should not be able to
        access the file system (which could be used to read database
        credentials or other sensitive data).
        """
        formula_logic = """
def calculate(distance, weight, context):
    try:
        f = open('/etc/passwd', 'r')
        return {'cost': 0, 'currency': 'USD', 'usd_cost': 0, 'file_access': True}
    except:
        pass
    return {'cost': 100.0, 'currency': 'USD', 'usd_cost': 100.0, 'file_access': False}
"""
        formula = create_test_formula(formula_logic)
        mock_db_session = mock_db_for_formula(formula)
        executor = create_executor(mock_db_session)

        result = executor.execute_formula(
            formula_id=formula.id,
            distance=distance,
            weight=weight,
            context=context,
        )

        assert result["file_access"] is False
