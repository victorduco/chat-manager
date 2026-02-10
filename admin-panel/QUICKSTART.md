# Quick Start Guide

## 🚀 Running the Admin Panel

### 1. Install dependencies

```bash
cd admin-panel
npm install
```

### 2. (Optional) Configure API URL

If you want to connect to a different LangGraph API server:

```bash
cp .env.example .env
# Edit .env and set VITE_LANGGRAPH_API_URL
```

Default: `https://langgraph-server.herokuapp.com`

### 3. Start the dev server

```bash
npm run dev
```

The app will open at http://localhost:3000

## 🎯 Using the Admin Panel

### Browse Threads

1. **Filter threads** using the left sidebar:
   - Select status: All, Idle, Busy, Interrupted, Error
   - Adjust limit (1-500 threads)
   - Click 🔄 Refresh to reload

2. **Click on any thread** to view details

### View Users & Intro Status

When you select a thread, you'll see:

- **User cards** with colored borders:
  - 🟢 Green border = Intro completed ✅
  - 🔴 Red border = Intro not completed ❌

- **User information**:
  - Full name and username
  - Telegram ID
  - Intro completion status
  - Additional profile data

### Thread Details

Each thread shows:
- Thread ID and metadata
- All users with their intro status
- Conversation summary
- Full message history

## 🛠️ Troubleshooting

### CORS Errors

If you see CORS errors in the console:

1. Make sure your LangGraph API allows requests from `localhost:3000`
2. Or deploy the admin panel to the same domain as your API
3. For development, you might need to configure CORS in your LangGraph deployment

### Connection Failed

If the app can't connect to the API:

1. Check that your LangGraph API is running
2. Verify the API URL in `.env` (or use default)
3. Test the API directly: `curl https://langgraph-server.herokuapp.com/threads/search -X POST -H "Content-Type: application/json" -d '{"limit":1}'`

### No Threads Found

This is normal if:
- Your LangGraph instance has no threads yet
- The selected filters exclude all threads
- Try changing the status filter to "All"

## 📱 Mobile View

The admin panel is responsive but works best on desktop/tablet due to the amount of information displayed.

## 🔒 Security Note

This is a local development tool. For production use:
- Add authentication
- Restrict API access to authorized IPs/users
- Use HTTPS
- Add rate limiting

## 💡 Tips

- Use the status filter to find specific threads (e.g., "Interrupted" to find threads needing attention)
- Increase the limit to see more threads at once (default: 100)
- Refresh regularly to see new threads
- Click on users to see their complete profile information
