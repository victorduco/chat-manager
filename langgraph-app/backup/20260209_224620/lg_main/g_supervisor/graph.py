from langgraph.graph import StateGraph, END, START
from conversation_states.states import ExternalState, InternalState
from langgraph.prebuilt import ToolNode
from .edges import should_summarize, should_use_profile_tools, route_actions
from .nodes import text_assistant, action_assistant, prepare_external, user_check, instruction_builder, profile_tools, proceed_to_assistants, prepare_internal


# Build graph
builder = StateGraph(InternalState, input=ExternalState, output=ExternalState)
builder.add_node("prepare_internal", prepare_internal)
builder.add_node("instruction_builder", instruction_builder)
builder.add_node("proceed_to_assistants", lambda state: state)
builder.add_node("text_assistant", text_assistant)
builder.add_node("action_assistant", action_assistant)
builder.add_node("user_check", user_check)
builder.add_node("profile_tools", ToolNode(
    profile_tools, messages_key="reasoning_messages"))
builder.add_node("prepare_external", prepare_external)


# Add edges
builder.add_edge(START, "prepare_internal")
builder.add_edge("prepare_internal", "instruction_builder")
builder.add_edge("instruction_builder", "proceed_to_assistants")


builder.add_conditional_edges(
    "proceed_to_assistants",
    route_actions  # text_assistant or/and action_assistant
)

builder.add_edge("text_assistant", "user_check")
builder.add_edge("action_assistant", "user_check")
builder.add_conditional_edges(
    "user_check",
    should_use_profile_tools
)
builder.add_edge("profile_tools", "user_check")

builder.add_edge("prepare_external", END)

# Compile graph
graph_supervisor = builder.compile()
