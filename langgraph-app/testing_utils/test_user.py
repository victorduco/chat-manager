"""Test user utilities for LangGraph manual testing.

This module provides utilities for creating test users when manually testing
LangGraph workflows. These should only be used in development/testing scenarios,
not in production code.
"""

from conversation_states import Human


def create_test_user() -> Human:
    """Create a test user for LangGraph manual testing.

    Returns:
        Human: A test user with predefined attributes.

    Note:
        This is intended for manual testing of LangGraph workflows only.
        Do not use in production code paths.
    """
    return Human(
        username="test_user",
        first_name="Test",
        last_name="User"
    )
