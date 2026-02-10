from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from conversation_states.states import InternalState
from .internal_edges import should_use_tools
from .internal_nodes import agent, load_categories, prime_turn, run_tools


builder = StateGraph(InternalState)
builder.add_node("load_categories", load_categories)
builder.add_node("prime_turn", prime_turn)
builder.add_node("agent", agent)
builder.add_node("tools", run_tools)

builder.add_edge(START, "load_categories")
builder.add_edge("load_categories", "prime_turn")
builder.add_edge("prime_turn", "agent")
builder.add_conditional_edges("agent", should_use_tools)

# After tools, return to the agent so it can read tool outputs and decide next step.
builder.add_edge("tools", "agent")

graph_chat_manager_internal = builder.compile()
