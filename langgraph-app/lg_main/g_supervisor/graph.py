from langgraph.graph import StateGraph, END, START
from conversation_states.states import ExternalState, InternalState
from .nodes import intro_checker, intro_responder, prepare_internal, prepare_external
from .edges import route_after_intro_checker
from lg_main.g_chat_manager.graph import graph_chat_manager


# Build graph
builder = StateGraph(InternalState, input=ExternalState, output=ExternalState)
builder.add_node("prepare_internal", prepare_internal)
builder.add_node("intro_checker", intro_checker)
builder.add_node("intro_responder", intro_responder)
builder.add_node("chat_manager", graph_chat_manager)
builder.add_node("prepare_external", prepare_external)


# Add edges
builder.add_edge(START, "prepare_internal")
builder.add_edge("prepare_internal", "intro_checker")
builder.add_conditional_edges("intro_checker", route_after_intro_checker)
builder.add_edge("intro_responder", "prepare_external")
builder.add_edge("chat_manager", "prepare_external")
builder.add_edge("prepare_external", END)

# Compile graph
graph_supervisor = builder.compile()
