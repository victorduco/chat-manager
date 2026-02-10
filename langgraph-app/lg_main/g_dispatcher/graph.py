from langgraph.graph import END, START, StateGraph

from conversation_states.states import ExternalState
from .edges import route_dispatch
from .nodes import dispatcher_router, dispatcher_default_reply
from lg_main.g_command_router.graph import graph_router
from lg_main.g_supervisor.graph import graph_supervisor


builder = StateGraph(ExternalState)

builder.add_node("dispatcher_router", dispatcher_router)
builder.add_node("dispatcher_default_reply", dispatcher_default_reply)
builder.add_node("graph_router", graph_router)
builder.add_node("graph_supervisor", graph_supervisor)

builder.add_edge(START, "dispatcher_router")
builder.add_conditional_edges("dispatcher_router", route_dispatch)

builder.add_edge("dispatcher_default_reply", END)
builder.add_edge("graph_router", END)
builder.add_edge("graph_supervisor", END)

graph_dispatcher = builder.compile()
