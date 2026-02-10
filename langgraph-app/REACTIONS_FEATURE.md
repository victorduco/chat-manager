# Reaction Feature

## Overview

The bot can now send emoji reactions to user messages via Telegram's native reaction API. This allows the bot to acknowledge messages with emotional responses without sending text messages.

## How It Works

### 1. Action Framework

**File**: `libs/conversation_states/conversation_states/actions.py`

The existing action framework supports reactions:
- `Action` class with `type` and `value` fields
- `ActionType` includes "reaction" among other types
- `Reaction` type with 70+ emoji options
- `ActionSender` class with `send_reaction()` method

### 2. New Tool: `send_user_reaction`

**File**: `langgraph-app/tool_sets/user_profile.py`

```python
@tool
def send_user_reaction(
    reaction_type: str,
    state: Annotated[InternalState, InjectedState]
) -> bool:
    """
    Send a reaction emoji to the user's message.

    Args:
    - reaction_type: "like", "dislike", "heart", "fire", "thinking", "laugh", "clap", "celebrate"
    """
```

**Available reactions:**
- `like` → 👍
- `dislike` → 👎
- `heart` → ❤
- `fire` → 🔥
- `thinking` → 🤔
- `laugh` → 🤣
- `clap` → 👏
- `celebrate` → 🎉

### 3. Integration with Graph

**File**: `langgraph-app/lg_main/g_supervisor/nodes.py`

The tool is registered in the `profile_tools` list and can be called by the LLM during the user_check phase.

### 4. Streaming Infrastructure

**Files**:
- `chatbot/event_handlers/utils/stream/stream_producer.py` - Produces actions from LangGraph
- `chatbot/event_handlers/utils/stream/stream_consumer.py` - Consumes and executes actions

The reaction is:
1. Queued by `stream_producer.queue_action()`
2. Consumed by `stream_consumer.run_actions()`
3. Sent via `reaction_responder()` using Telegram's `set_reaction()` API

## Usage Examples

### When the LLM should send reactions:

1. **Acknowledging without interrupting conversation:**
   ```
   User A: "Hey @UserB, want to grab lunch?"
   Bot: [Sends 👍 reaction, doesn't send text message]
   ```

2. **Showing empathy:**
   ```
   User: "I just finished a difficult project!"
   Bot: [Sends 🎉 reaction] + text response: "Congratulations! How did it go?"
   ```

3. **Quick emotional response:**
   ```
   User: "This bug is driving me crazy"
   Bot: [Sends 🤔 reaction] + text response: "Let me help you debug it"
   ```

## Technical Flow

```
User message
    ↓
LangGraph processing
    ↓
user_check node (with profile_tools)
    ↓
LLM calls send_user_reaction(reaction_type="like")
    ↓
Tool uses ActionSender to queue reaction
    ↓
StreamProducer emits action event
    ↓
StreamConsumer.queue_action() receives it
    ↓
reaction_responder() sends via Telegram API
    ↓
User sees reaction on their message
```

## Important Notes

1. **Not a text message**: Reactions appear directly on the user's message, not as a separate message
2. **Via callback**: Uses Telegram's `set_reaction()` API (callback mechanism), not text messages
3. **Can combine**: Bot can send both a reaction AND a text response
4. **LLM decides**: The LLM chooses when to send reactions based on context

## Testing

1. Send a message to the bot
2. If appropriate, the bot may send a reaction (e.g., 👍 or ❤) to your message
3. The reaction should appear on your message (not as a separate message)
4. Check logs to verify the action is queued and processed:
   ```
   DEBUG: Action queued: {"type": "reaction", "value": "👍"}
   ```

## Configuration

To add more reaction types, edit:

**File**: `langgraph-app/tool_sets/user_profile.py`

```python
reaction_map = {
    "like": "👍",
    "dislike": "👎",
    "your_new_type": "🎯"  # Add here
}
```

## Future Improvements

- [ ] Add tool for automated reactions based on sentiment analysis
- [ ] Allow users to configure preferred reaction types
- [ ] Add analytics for reaction usage
- [ ] Support reaction sequences (multiple reactions on same message)
