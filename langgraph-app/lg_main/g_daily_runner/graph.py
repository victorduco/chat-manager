from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage

from conversation_states.states import ExternalState


def hello_world(state: ExternalState) -> ExternalState:
    # Test daily runner: minimal output for cron-triggered runs.
    # Future: route into per-thread dispatch graph, inject summary/tasks, etc.
    return ExternalState(
        messages=[
            AIMessage(content="hello world", name="daily_runner"),
        ],
        users=list(state.users),
        summary=state.summary,
        last_reasoning=state.last_reasoning,
        memory_records=list(getattr(state, "memory_records", []) or []),
    )


builder = StateGraph(ExternalState)
builder.add_node("hello_world", hello_world)
builder.add_edge(START, "hello_world")
builder.add_edge("hello_world", END)

graph_daily_runner = builder.compile()

