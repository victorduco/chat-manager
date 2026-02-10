from langgraph.graph import StateGraph, END, START
from conversation_states.states import ExternalState
from .nodes import dispatch


# Build graph
builder = StateGraph(ExternalState)
builder.add_node("dispatch", dispatch)

# Add edges
builder.add_edge(START, "dispatch")
builder.add_edge("dispatch", END)

# Compile graph
graph_dispatcher = builder.compile()

