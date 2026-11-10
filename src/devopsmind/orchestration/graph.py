import uuid
import sqlite3
from typing import List, Dict, Any, TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END
from src.devopsmind.config import settings
from src.devopsmind.database.sqlite import init_db
from src.devopsmind.schemas.findings import Finding
from src.devopsmind.agents.code_review_agent import CodeReviewAgent
from src.devopsmind.agents.security_agent import SecurityAgent
from src.devopsmind.agents.architecture_agent import ArchitectureAgent
from src.devopsmind.agents.test_gen_agent import TestGenerationAgent
from src.devopsmind.agents.log_agent import LogAnalysisAgent

# Define Shared State across Graph Nodes
class DevOpsState(TypedDict):
    run_id: str
    target_path: str
    log_path: str
    findings: List[Finding]
    graph_metadata: Dict[str, Any]
    status: str

def run_code_review_node(state: DevOpsState) -> DevOpsState:
    print("\n[LangGraph] Executing CodeReviewAgent node...")
    agent = CodeReviewAgent(run_id=state["run_id"])
    findings = agent.analyze(state["target_path"])
    state["findings"].extend(findings)
    return state

def run_security_node(state: DevOpsState) -> DevOpsState:
    print("\n[LangGraph] Executing SecurityAgent node...")
    agent = SecurityAgent(run_id=state["run_id"])
    findings = agent.analyze(state["target_path"])
    state["findings"].extend(findings)
    return state

def run_architecture_node(state: DevOpsState) -> DevOpsState:
    print("\n[LangGraph] Executing ArchitectureAgent node...")
    agent = ArchitectureAgent(run_id=state["run_id"])
    findings, meta = agent.analyze(state["target_path"])
    state["findings"].extend(findings)
    state["graph_metadata"] = meta
    return state

def run_test_gen_node(state: DevOpsState) -> DevOpsState:
    print("\n[LangGraph] Executing TestGenerationAgent node...")
    agent = TestGenerationAgent(run_id=state["run_id"])
    findings = agent.generate_and_execute_tests(state["target_path"])
    state["findings"].extend(findings)
    return state

def run_log_analysis_node(state: DevOpsState) -> DevOpsState:
    print("\n[LangGraph] Executing LogAnalysisAgent node...")
    agent = LogAnalysisAgent(run_id=state["run_id"])
    findings = agent.analyze(state["log_path"])
    state["findings"].extend(findings)
    state["status"] = "COMPLETED"
    return state

def persist_results_node(state: DevOpsState) -> DevOpsState:
    print("\n[LangGraph] Persisting consolidated findings to SQLite...")
    init_db()
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR REPLACE INTO analysis_runs VALUES (?, ?, ?, ?, ?)",
        (state["run_id"], "DevOpsMind-LangGraph-Pipeline", datetime.now().isoformat(), 85, state["status"])
    )

    for f in state["findings"]:
        cursor.execute(
            """INSERT OR REPLACE INTO agent_findings 
               (finding_id, run_id, agent_name, severity, file_path, line_number, title, description, recommended_fix, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (f.id, f.run_id, f.agent_name, f.severity, f.file_path, f.line_number, f.title, f.description, f.recommended_fix, f.timestamp)
        )

    conn.commit()
    conn.close()
    print(f"[LangGraph] Successfully persisted {len(state['findings'])} total findings!")
    return state

def build_devops_graph(skip_test_execution: bool = True):
    workflow = StateGraph(DevOpsState)

    # Add Nodes
    workflow.add_node("code_review", run_code_review_node)
    workflow.add_node("security", run_security_node)
    workflow.add_node("architecture", run_architecture_node)
    if not skip_test_execution:
        workflow.add_node("test_gen", run_test_gen_node)
    workflow.add_node("log_analysis", run_log_analysis_node)
    workflow.add_node("persist", persist_results_node)

    # Define Workflow Edges (Sequential pipeline or fan-out/fan-in)
    workflow.set_entry_point("code_review")
    workflow.add_edge("code_review", "security")
    workflow.add_edge("security", "architecture")
    if skip_test_execution:
        workflow.add_edge('architecture', 'log_analysis')
    else:
        workflow.add_edge('architecture', 'test_gen')
    if not skip_test_execution:
        workflow.add_edge("test_gen", "log_analysis")
    workflow.add_edge("log_analysis", "persist")
    workflow.add_edge("persist", END)

    return workflow.compile()