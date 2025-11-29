# Testing Utilities

This directory contains utilities for manual testing of LangGraph workflows.

## Purpose

These utilities are used during LangGraph development and manual testing when a user object is required but no real user is available in the state.

## Usage

### test_user.py

Provides a `create_test_user()` function that returns a `Human` object with predefined test attributes.

```python
from testing_utils import create_test_user

# Create a test user for manual testing
test_user = create_test_user()
```

## Important Notes

⚠️ **Development Only**: These utilities are intended for development and manual testing scenarios only.

⚠️ **Not for Production**: Do not rely on these in production code paths. The test user is automatically added in `prepare_internal()` function only when the user list is empty, which should only occur during manual LangGraph testing.

## Why This Exists

When manually testing LangGraph workflows through the API, the state may not always include a user object. This utility ensures that workflows can proceed without errors during development and testing.
