# Changelog

## [Unreleased] - 2026-02-09

### Added
- **Intro Reminder Feature**: Bot now tracks whether users have written their introduction
  - New `intro_completed` field in `Human` model
  - New `mark_intro_completed()` tool to mark intro as done
  - New `intro_checker` node in supervisor graph
  - Automatic gentle reminder after 2+ meaningful messages if intro not completed

### Changed
- Updated `graph_supervisor` flow:
  - `text_assistant` → `intro_checker` → `user_check` → ...
- Enhanced `user_check` prompt to detect introductions and call `mark_intro_completed()`
- Updated `profile_tools` list to include `mark_intro_completed`

### Backup
- Created backup at `langgraph-app/backup/20260209_224620/`
  - `lg_main/` - All graph definitions
  - `prompt_templates/` - All prompts
  - `tool_sets/` - All tools

## Previous Versions

Initial release with basic functionality.
