# Intro Reminder Feature

## Overview

The bot now tracks whether users have written their introduction and gently reminds them after a few messages if they haven't.

## How It Works

### 1. User Model Update

**File**: `libs/conversation_states/conversation_states/humans.py`

```python
class Human(BaseModel):
    username: str
    first_name: str
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    information: Dict = Field(default_factory=dict)
    intro_completed: bool = False  # ← New field
```

### 2. New Tool: `mark_intro_completed`

**File**: `langgraph-app/tool_sets/user_profile.py`

```python
@tool
def mark_intro_completed(state: Annotated[InternalState, InjectedState]) -> bool:
    """Mark that the user has completed their introduction."""
    sender = state.last_sender
    if not sender:
        return False
    sender.intro_completed = True
    return True
```

### 3. Updated Graph Flow

**File**: `langgraph-app/lg_main/g_supervisor/graph.py`

```
text_assistant
    ↓
intro_checker (NEW)  ← Checks if reminder needed
    ↓
user_check
    ↓
profile_tools (includes mark_intro_completed)
    ↓
prepare_external
```

### 4. Intro Checker Node

**File**: `langgraph-app/lg_main/g_supervisor/nodes.py`

The `intro_checker` node:
- Skips if `intro_completed == True`
- Counts meaningful messages from user (>10 chars)
- After 2+ messages without intro, adds gentle reminder to response
- Regenerates response with intro request appended

### 5. Detection Logic

**File**: `langgraph-app/prompt_templates/prompt_builder.py`

The `user_check` prompt now includes:
- Intro status tracking
- Instructions to detect introductions
- Call `mark_intro_completed()` when user shares their intro

**What counts as an intro:**
- User shares 2+ personal facts in one message
- Examples:
  - "I'm a software engineer from Berlin, love hiking"
  - "Hey, I'm Alex. I work in design and I'm into AI"

## User Flow Example

### Scenario 1: User writes intro immediately

```
User: "Hi! I'm Alex from Berlin, software engineer, love hiking"
Bot: "Nice to meet you, Alex! ..."
[Calls: update_user_info() + mark_intro_completed()]
[intro_completed = True]
```

### Scenario 2: User doesn't write intro

```
User: "привет"
Bot: "Привет! Как дела?"

User: "хорошо"
Bot: "Рад слышать! ..."

User: "что нового?"
Bot: "У меня все отлично! By the way, I'd love to know more
     about you! Could you share a bit about yourself?"
[intro_checker added reminder after 2+ messages]

User: "Я из Москвы, работаю программистом, люблю читать"
Bot: "Круто! ..."
[Calls: mark_intro_completed()]
```

## Configuration

### Reminder Threshold

**File**: `langgraph-app/lg_main/g_supervisor/nodes.py:121`

```python
if len(user_messages) >= 2:  # ← Change this number
```

### Reminder Text

**File**: `langgraph-app/lg_main/g_supervisor/nodes.py:127-133`

Modify the SystemMessage content to change the reminder style.

## Testing

### Check Intro Status

Use `/show_context` command to see user's intro status:

```
👤 Users:
- Victor Duco (ducov)
  - preferred_name: not provided
  - intro_completed: False  ← Shows status
  - info: {...}
```

### Manual Testing

1. Send a few short messages (should trigger reminder)
2. Send an introduction message
3. Check `/show_context` - should show `intro_completed: True`
4. Send more messages - no more reminders

## Rollback

If you need to rollback to the previous version:

```bash
cd langgraph-app
rm -rf lg_main prompt_templates tool_sets
cp -r backup/20260209_224620/* ./
```

## Future Improvements

- [ ] Make reminder threshold configurable per user
- [ ] Add different reminder styles based on user preferences
- [ ] Track intro quality/completeness
- [ ] Allow users to skip intro requirement
