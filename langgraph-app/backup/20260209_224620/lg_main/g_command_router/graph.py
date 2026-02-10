from langgraph.graph import StateGraph, END, START
from conversation_states.states import ExternalState
from .edges import route_command
from .nodes import clear_context, clear_context_prep, show_context, show_context_prep
from .nodes import show_thinking, show_thinking_prep, router
import os


# Build graph
builder = StateGraph(ExternalState)
builder.add_node("router", router)
builder.add_node("clear_context_prep", clear_context_prep)
builder.add_node("clear_context", clear_context)
builder.add_node("show_context_prep", show_context_prep)
builder.add_node("show_context", show_context)
builder.add_node("show_thinking_prep", show_thinking_prep)
builder.add_node("show_thinking", show_thinking)
builder.add_node("wrong_command", lambda state: state)

# Add edges
builder.add_edge(START, "router")
builder.add_conditional_edges(
    "router",
    route_command
)


builder.add_edge("clear_context_prep", "clear_context")
builder.add_edge("show_context_prep", "show_context")
builder.add_edge("show_thinking_prep", "show_thinking")

builder.add_edge("clear_context", END)
builder.add_edge("show_context", END)
builder.add_edge("show_thinking", END)
builder.add_edge("wrong_command", END)


# Compile graph
graph_router = builder.compile()
