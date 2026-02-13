from langgraph.graph import StateGraph, END, START
from conversation_states.states import ExternalState, InternalState
from .nodes import (
    intro_checker,
    intro_quality_guard,
    intro_quality_reprompt,
    intro_responder,
    prepare_internal,
    prepare_external,
)
from .edges import (
    route_after_intro_checker,
    route_after_intro_quality_guard,
    route_after_mention_checker,
    route_after_mentioned_quality_guard,
    route_after_unmentioned_relevance_guard,
)
from lg_main.g_chat_manager.internal_graph import graph_chat_manager_internal
from .nodes import no_intro, mention_checker, mentioned_quality_guard, unmentioned_relevance_guard, mentioned_block_response


# Build graph
builder = StateGraph(InternalState, input=ExternalState, output=ExternalState)
builder.add_node("prepare_internal", prepare_internal)
builder.add_node("intro_checker", intro_checker)
builder.add_node("intro_quality_guard", intro_quality_guard)
builder.add_node("intro_quality_reprompt", intro_quality_reprompt)
builder.add_node("intro_responder", intro_responder)
builder.add_node("no_intro", no_intro)
builder.add_node("mention_checker", mention_checker)
builder.add_node("mentioned_quality_guard", mentioned_quality_guard)
builder.add_node("unmentioned_relevance_guard", unmentioned_relevance_guard)
builder.add_node("mentioned_block_response", mentioned_block_response)
builder.add_node("chat_manager", graph_chat_manager_internal)
builder.add_node("prepare_external", prepare_external)


# Add edges
builder.add_edge(START, "prepare_internal")
builder.add_edge("prepare_internal", "intro_checker")
builder.add_conditional_edges("intro_checker", route_after_intro_checker)
builder.add_conditional_edges("intro_quality_guard", route_after_intro_quality_guard)
builder.add_edge("intro_responder", "prepare_external")
builder.add_edge("intro_quality_reprompt", "prepare_external")
builder.add_edge("no_intro", "prepare_external")
builder.add_conditional_edges("mention_checker", route_after_mention_checker)
builder.add_conditional_edges("mentioned_quality_guard", route_after_mentioned_quality_guard)
builder.add_conditional_edges("unmentioned_relevance_guard", route_after_unmentioned_relevance_guard)
builder.add_edge("mentioned_block_response", "prepare_external")
builder.add_edge("chat_manager", "prepare_external")
builder.add_edge("prepare_external", END)

# Compile graph
graph_supervisor = builder.compile()
