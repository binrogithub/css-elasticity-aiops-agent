"""LangGraph workflow construction."""

from langgraph.graph import END, StateGraph

from app.nodes.ai_decide import ai_decide_node
from app.nodes.build_history_summary import build_history_summary_node
from app.nodes.check_pending_operation import check_pending_operation_node
from app.nodes.collect_metrics import collect_metrics_node
from app.nodes.detect_spike import detect_spike_node
from app.nodes.execute_action import execute_action_node
from app.nodes.finalize_state import finalize_state_node
from app.nodes.persist_run import persist_run_node
from app.nodes.should_run_ai_review import route_after_should_run_ai, should_run_ai_review_node
from app.nodes.verify_result import verify_result_node
from app.runtime import Runtime
from app.state import AgentState


def build_graph(runtime: Runtime):
    graph = StateGraph(AgentState)
    graph.add_node("collect_metrics", collect_metrics_node(runtime))
    graph.add_node("check_pending_operation", check_pending_operation_node(runtime))
    graph.add_node("detect_spike", detect_spike_node(runtime))
    graph.add_node("build_history_summary", build_history_summary_node(runtime))
    graph.add_node("should_run_ai_review", should_run_ai_review_node(runtime))
    graph.add_node("ai_decide", ai_decide_node(runtime))
    graph.add_node("execute_action", execute_action_node(runtime))
    graph.add_node("verify_result", verify_result_node(runtime))
    graph.add_node("persist_run", persist_run_node(runtime))
    graph.add_node("finalize_state", finalize_state_node(runtime))

    graph.set_entry_point("collect_metrics")
    graph.add_edge("collect_metrics", "check_pending_operation")
    graph.add_edge("check_pending_operation", "detect_spike")
    graph.add_edge("detect_spike", "build_history_summary")
    graph.add_edge("build_history_summary", "should_run_ai_review")
    graph.add_conditional_edges(
        "should_run_ai_review",
        route_after_should_run_ai,
        {"ai_decide": "ai_decide", "persist_run": "persist_run"},
    )
    graph.add_edge("ai_decide", "execute_action")
    graph.add_edge("execute_action", "verify_result")
    graph.add_edge("verify_result", "persist_run")
    graph.add_edge("persist_run", "finalize_state")
    graph.add_edge("finalize_state", END)
    return graph.compile()
