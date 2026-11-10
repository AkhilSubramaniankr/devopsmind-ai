import uuid
from src.devopsmind.config import settings
from src.devopsmind.orchestration.graph import build_devops_graph

def run_master_pipeline():
    print(f"=== {settings.PROJECT_NAME} — LangGraph Master Orchestration Pipeline ===")
    
    run_id = str(uuid.uuid4())
    target_path = str(settings.BASE_DIR / "src")
    log_path = str(settings.BASE_DIR / "logs" / "build_error.log")

    initial_state = {
        "run_id": run_id,
        "target_path": target_path,
        "log_path": log_path,
        "findings": [],
        "graph_metadata": {},
        "status": "INITIALIZED"
    }

    # Compile and Invoke LangGraph
    app = build_devops_graph()
    print(f"Executing workflow for run ID: {run_id}")
    
    final_state = app.invoke(initial_state)

    print(f"\n=== Master Orchestration Complete! ===")
    print(f"Run ID: {final_state['run_id']}")
    print(f"Total Findings Collected & Stored: {len(final_state['findings'])}")
    print(f"Architecture Nodes: {final_state['graph_metadata'].get('node_count', 0)}")

if __name__ == "__main__":
    run_master_pipeline()