# Development Scripts

This directory contains utility scripts for development and testing purposes.

## ⚠️ Warning

These scripts are **development tools only** and should be used with caution.

## Scripts

### delete_all_threads.py

**Purpose:** Deletes ALL threads from the LangGraph API.

**Use case:** Cleaning up test data during development.

**Warning:** This is a destructive operation that will delete all conversation threads. Only use in development/testing environments, never in production.

**Usage:**
```bash
python scripts/delete_all_threads.py
```

**Requirements:**
- `LANGGRAPH_API_URL` environment variable must be set
- Requires `requests` library

**What it does:**
1. Searches for all threads in the LangGraph API
2. Deletes each thread one by one
3. Continues until no threads remain

**Safety note:** Always verify you're connected to the correct API endpoint before running this script.
