from typing import Annotated
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from conversation_states.states import InternalState
from conversation_states.humans import Human


@tool
def set_preferred_name(
    preferred_name: str,
    state: Annotated[InternalState, InjectedState]
) -> bool:
    """
    Set or update the user's preferred name based on their message.

    Args:
    - preferred_name: str (e.g., "Max")

    Output:
    - True | False — Success or not

    Examples:
    >>> set_preferred_name(preferred_name="Max")
    True
    """
    try:
        sender = state.last_sender
        if not sender:
            return False
        sender.preferred_name = preferred_name
        return True
    except Exception:
        return False


@tool
def update_user_info(
    fields: list[dict[str, str]],
    state: Annotated[InternalState, InjectedState]
) -> bool:
    """
    Add, Edit or Delete persistent personal information about the user.

    Args:
    - fields: list[dict[str, str]] — one or more key-value pairs such as {"location": "Lisbon"}, {"profession": "UX designer"}

    Instructions:
    - You can pass more than one field at a time by including multiple dictionaries in the list.
    - You can delete a record by sending the empty value for the key
    - You can edit a record by sending a new value for the key
    - Don't replace or remove info if the new details don't contradict with it. 

    Output:
    - True | False — Success or not

    Examples:
    >>> update_user_info(fields=[{"location": "Lisbon"}])  // if user said "I live in lisbon"
    True

    >>> update_user_info(fields=[{"location": "Lisbon"}, {"profession": "UX designer"}]) // if user said "Hey guys, do you know open UX designer positions in Lisbon?"
    True

    >>> update_user_info(fields=[{"married": ""}]) // if user said "I'm not married anymore"
    True

    >>> update_user_info(fields=[{"food preferences": "Italian, Pizza"}]) // It was {"food preferences": "Italian"} and user said "Hey Alex, want to grab pizza tonight?"
    True
    """
    try:
        sender = state.last_sender
        if not sender:
            return False
        sender.update_info(fields)
        return True
    except Exception:
        return False


@tool
def mark_intro_completed(
    state: Annotated[InternalState, InjectedState]
) -> bool:
    """
    Mark that the user has completed their introduction.

    Call this tool when the user provides their introduction (tells about themselves,
    their interests, background, etc.).

    Output:
    - True | False — Success or not

    Examples:
    >>> mark_intro_completed()
    True
    """
    try:
        sender = state.last_sender
        if not sender:
            return False
        sender.intro_completed = True
        return True
    except Exception:
        return False


@tool
def send_user_reaction(
    reaction_type: str,
    state: Annotated[InternalState, InjectedState]
) -> bool:
    """
    Send a reaction emoji to the user's message.

    Args:
    - reaction_type: str - The type of reaction to send. Options: "like" (👍), "dislike" (👎), "heart" (❤), "fire" (🔥), "thinking" (🤔), "laugh" (🤣), "clap" (👏), "celebrate" (🎉)

    Use this when you want to acknowledge the user's message with an emoji reaction.
    This is useful for showing emotional response without sending a text message.

    Output:
    - True | False — Success or not

    Examples:
    >>> send_user_reaction(reaction_type="like")
    True

    >>> send_user_reaction(reaction_type="heart")
    True

    >>> send_user_reaction(reaction_type="thinking")
    True
    """
    from conversation_states.actions import ActionSender, Action
    from langgraph.types import StreamWriter

    reaction_map = {
        "like": "👍",
        "dislike": "👎",
        "heart": "❤",
        "fire": "🔥",
        "thinking": "🤔",
        "laugh": "🤣",
        "clap": "👏",
        "celebrate": "🎉"
    }

    try:
        # Get the writer from state
        writer = state.get("writer")
        if not writer:
            return False

        # Get the reaction emoji
        reaction = reaction_map.get(reaction_type)
        if not reaction:
            return False

        # Send the reaction
        sender = ActionSender(writer)
        sender.send_reaction(reaction)
        return True
    except Exception:
        return False
