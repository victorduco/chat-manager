# LangGraph Admin Panel

Web-based admin panel for managing LangGraph threads and viewing user intro status.

## Features

- 📋 **Thread List**: Browse all threads with filters (status, limit)
- 👥 **User Management**: View all users in each thread with their intro status
- ✅ **Intro Status**: Visual indicators for completed/incomplete intros
- 💬 **Message History**: View conversation history
- 📝 **Thread Details**: Full thread state and metadata
- 🎨 **Clean UI**: Modern, responsive design

## Setup

### Prerequisites

- Node.js 18+ or npm/yarn/pnpm
- Access to LangGraph API endpoint

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment (optional):
```bash
cp .env.example .env
# Edit .env to set your LangGraph API URL
```

Default API URL: `https://langgraph-server.herokuapp.com`

### Development

Run the development server:
```bash
npm run dev
```

This will start the app at http://localhost:3000

### Production Build

Build for production:
```bash
npm run build
```

Preview production build:
```bash
npm run preview
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
VITE_LANGGRAPH_API_URL=https://your-langgraph-server.com
```

If not set, defaults to production URL.

### Local Development with LangGraph API

To connect to a local LangGraph instance:

```env
VITE_LANGGRAPH_API_URL=http://localhost:2024
```

## Usage

1. **Browse Threads**:
   - Use filters in the left sidebar to filter by status
   - Adjust limit to load more/fewer threads
   - Click refresh to reload

2. **View Thread Details**:
   - Click on any thread in the list
   - View users with intro status (✅ completed, ❌ not completed)
   - See full conversation history
   - Check thread metadata and state

3. **User Info**:
   - Each user card shows:
     - Name and username
     - Telegram ID
     - Intro completion status
     - Additional profile information
     - Preferred name (if set)

## API Endpoints Used

The admin panel uses the following LangGraph Platform API endpoints:

- `POST /threads/search` - Search and filter threads
- `GET /threads/{thread_id}` - Get thread info
- `GET /threads/{thread_id}/state` - Get detailed thread state
- `GET /threads/{thread_id}/history` - Get thread history

**Note**: No additional server-side code required! The panel connects directly to the LangGraph API.

## Project Structure

```
admin-panel/
├── src/
│   ├── components/
│   │   ├── ThreadsList.vue      # Thread list with filters
│   │   └── ThreadDetails.vue    # Thread details and users
│   ├── services/
│   │   └── api.js               # LangGraph API service
│   ├── App.vue                  # Main app component
│   └── main.js                  # App entry point
├── index.html
├── vite.config.js
├── package.json
└── README.md
```

## Technologies

- **Vue 3** - Progressive JavaScript framework
- **Vite** - Fast build tool
- **Axios** - HTTP client
- **Composition API** - Modern Vue reactivity

## CORS Considerations

If you encounter CORS issues when connecting to LangGraph API:

1. For development, you can use a CORS proxy
2. Configure your LangGraph API server to allow requests from localhost:3000
3. Deploy the admin panel to the same domain as your API

## License

Same as parent project (GPL-3.0)
