from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from conversation_states.states import InternalState
from tool_sets.chat_memory import add_memory_record, list_memory_records

from .internal_edges import should_use_tools
from .internal_nodes import agent, load_categories


_tools_node = ToolNode([add_memory_record, list_memory_records], messages_key="reasoning_messages")

builder = StateGraph(InternalState)
builder.add_node("load_categories", load_categories)
builder.add_node("agent", agent)
builder.add_node("tools", _tools_node)

builder.add_edge(START, "load_categories")
builder.add_edge("load_categories", "agent")
builder.add_conditional_edges("agent", should_use_tools)

# After tools, refresh categories (they may have changed) and let the agent decide next step.
builder.add_edge("tools", "load_categories")

builder.add_edge("agent", END)

graph_chat_manager_internal = builder.compile()

