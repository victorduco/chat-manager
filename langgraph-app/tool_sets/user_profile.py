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
