from __future__ import annotations

from pydantic import Field
from langgraph.graph import END, START, StateGraph

from conversation_states.states import ExternalState
from lg_main.g_daily_meta_improver.graph import graph_daily_meta_improver
from lg_main.g_daily_summary.graph import graph_daily_summary


class DailyRunnerState(ExternalState):
    # Inputs for the metadata improver subgraph.
    thread_meta: dict = Field(default_factory=dict)
    thread_info_entries_input: list[str] = Field(default_factory=list)
    thread_info_entries_reviewed: list[str] = Field(default_factory=list)

    # Shared daily window for both subgraphs.
    window_since_utc: str | None = None
    window_until_utc: str | None = None


def node_strip_improver_context(_: DailyRunnerState) -> dict:
    # Ensure daily_summary does not receive improver-specific context.
    return {
        "thread_meta": {},
        "thread_info_entries_input": [],
        "thread_info_entries_reviewed": [],
    }


builder = StateGraph(DailyRunnerState)
builder.add_node("meta_improver", graph_daily_meta_improver)
builder.add_node("strip_improver_context", node_strip_improver_context)
builder.add_node("daily_summary", graph_daily_summary)

builder.add_edge(START, "meta_improver")
builder.add_edge("meta_improver", "strip_improver_context")
builder.add_edge("strip_improver_context", "daily_summary")
builder.add_edge("daily_summary", END)

graph_daily_runner = builder.compile()
