from langgraph.graph import END, START, StateGraph

from conversation_states.states import InternalState
from .edges import route_chat_manager
from .nodes import decide_intent, add_record, list_records, list_categories, unhelpful


builder = StateGraph(InternalState)
builder.add_node("decide_intent", decide_intent)
builder.add_node("add_record", add_record)
builder.add_node("list_records", list_records)
builder.add_node("list_categories", list_categories)
builder.add_node("unhelpful", unhelpful)

builder.add_edge(START, "decide_intent")
builder.add_conditional_edges("decide_intent", route_chat_manager)

builder.add_edge("add_record", END)
builder.add_edge("list_records", END)
builder.add_edge("list_categories", END)
builder.add_edge("unhelpful", END)

graph_chat_manager = builder.compile()

