# Admin Panel Changelog

## [Unreleased] - 2026-02-10

### Added
- **Environment Switcher**: Added DEV/PROD toggle in header
  - 🔧 DEV mode: Connects to local LangGraph API at `http://localhost:2024`
  - 🚀 PROD mode: Connects to Heroku at `https://langgraph-server-611bd1822796.herokuapp.com`
  - Environment preference is saved in browser's localStorage
  - Automatically reloads thread list when switching environments

### Changed
- Updated API service to support dynamic environment switching
- Modified header layout to include environment toggle buttons
- Enhanced responsive design for mobile devices

### Technical Details
- Added `getCurrentEnvironment()`, `setEnvironment()`, `getCurrentApiUrl()` functions to API service
- Environment selection persists across browser sessions
- Custom event `api-environment-changed` for cross-tab synchronization
