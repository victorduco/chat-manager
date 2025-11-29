# TODO List

This file contains all TODO items extracted from code comments, organized by component.

## Chatbot Component

### Telegram Connector - Local Development Setup
**File:** `chatbot/messenger_connector/connectorClasses.py:58`
**Priority:** High

**Issue:** Local development polling mode doesn't work properly. The current code calls `run_polling()` before setting up commands and handlers, which means handlers aren't registered when polling starts.

**Current problematic flow:**
```python
# Line 61: This starts polling immediately
self.app.run_polling()
# Lines 62-64: These run after polling has started
await self.app.bot.set_my_commands(TELEGRAM_COMMANDS, BotCommandScopeDefault())
for handler in TELEGRAM_HANDLERS:
    self.app.add_handler(handler)
```

**Required fix:** Reorder the initialization so commands and handlers are set up before starting polling.

---

### Message Handler Architecture Redesign
**File:** `chatbot/event_handlers/message_handler.py:32-65`
**Priority:** Medium

**Description:** Architectural notes for redesigning the message handling system to support multiple content types.

**Proposed Architecture:**

**Content Types to Support:**
- Messages/chunks (type: message, with message ID and content type)
- Reactions (type: reaction, with reaction type)
- Photos (type: photo, with photo code or link)
- Voice messages (type: voice, with code or link)

**Producer Component:**
- Takes items from stream
- If chunk: puts directly into queue
- If reaction/photo/voice: puts entire object into queue
- Need to understand how to collect different types from stream

**Consumer Component:**
- Parses queue and delivers to corresponding handlers
- Message updates, reaction sending, etc.
- `message_responder`:
  - Receives message updates
  - Checks if old message (update) or new message
  - One instance per message
  - Initialization handles first chunk (check for length) and determines message type
  - Can also handle error type messages separately
- `reaction_responder`:
  - Similar pattern but only executes once
  - Object created and completes work in initialization

**Message Flow:**
1. Two handlers call content processor and pass content + type
2. Message arrives → call stream runner with chat object
   - If command → send to graph router
   - If text → send to supervisor
3. Create stream and receive chunks
4. Producer processes stream items
5. Consumer delivers to appropriate handlers

---

### Logging Configuration
**File:** `chatbot/event_handlers/message_handler.py:16`
**Priority:** Low

**Issue:** Logging configuration is commented out. Either enable it or remove if not needed.

**Commented line:**
```python
# enable_meowx(disable_labels=["MEOW TG"], show_core=False, show_content=True)
```

**Action required:** Decide whether to enable this logging or remove the commented code.

---

## LangGraph-app Component

### Test User in Production Code
**File:** `langgraph-app/lg_main/g_supervisor/nodes.py:20-27`
**Priority:** High

**Issue:** Test user is hardcoded in production code path. This test user gets added whenever the user list is empty.

**Current code:**
```python
if not state.users:
    test_user = Human(
        username="test_user",
        first_name="Test",
        last_name="User"
    )
    state.users.append(test_user)
```

**Solution:** Extract to dedicated testing utility file (`langgraph-app/testing_utils/test_user.py`) for use in LangGraph manual testing scenarios only.

---

## Libs/conversation_states Component

### GlobalInstructionList Design Question
**File:** `libs/conversation_states/conversation_states/store_schemas/instruction.py:30`
**Priority:** Low

**Issue:** Unclear if `GlobalInstructionList` class is needed.

**Current code:**
```python
class GlobalInstructionList(InstructionList):
    # TODO needed?
    pass
```

**Action required:** Either:
- Document why this class exists and what it's used for
- Remove it if it's not actually needed
- Implement additional functionality if required
