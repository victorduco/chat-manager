from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from conversation_states.states import InternalState
from .internal_edges import should_use_tools
from .internal_nodes import doer, load_categories, prime_turn, responder, run_tools


builder = StateGraph(InternalState)
builder.add_node("load_categories", load_categories)
builder.add_node("prime_turn", prime_turn)
builder.add_node("doer", doer)
builder.add_node("tools", run_tools)
builder.add_node("responder", responder)

builder.add_edge(START, "load_categories")
builder.add_edge("load_categories", "prime_turn")
builder.add_edge("prime_turn", "doer")
builder.add_conditional_edges("doer", should_use_tools)

# After tools, return to doer so it can read tool outputs and decide next step.
builder.add_edge("tools", "doer")
builder.add_edge("responder", END)

graph_chat_manager_internal = builder.compile()
