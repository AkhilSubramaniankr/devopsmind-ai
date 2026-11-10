"""DevOpsMind AI dashboard. Run: streamlit run src/devopsmind/ui/app.py"""
from __future__ import annotations

import uuid
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Supports both running from repository root and editable package installs.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.devopsmind.config import settings

st.set_page_config(page_title="DevOpsMind AI", page_icon="ðŸ§ ", layout="wide")
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Read only. SQLite database is never initialized or modified by dashboard reads."""
    db = Path(settings.DB_PATH)
    if not db.is_file():
        return pd.DataFrame()
    try:
        with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=5) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except (sqlite3.Error, pd.errors.DatabaseError) as exc:
        st.error(f"Could not read the database: {exc}")
        return pd.DataFrame()


def health_gauge(value: int | float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=float(value),
        number={"suffix": "/100"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#3878c6"}},
        title={"text": "Recorded health score"},
    ))
    fig.update_layout(height=260, margin=dict(l=25, r=25, t=65, b=15))
    return fig


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    runs = query("SELECT run_id, project_name, timestamp, health_score, status FROM analysis_runs ORDER BY timestamp DESC")
    findings = query("""SELECT finding_id, run_id, agent_name, severity, file_path,
                        line_number, title, description, recommended_fix, timestamp
                        FROM agent_findings ORDER BY timestamp DESC""")
    return runs, findings


def trigger_analysis(repo_path: Path, log_path: Path) -> dict:
    """Invoke the real graph, with untrusted test execution disabled."""
    from src.devopsmind.orchestration.graph import build_devops_graph

    repo = repo_path.expanduser().resolve(strict=True)
    if not repo.is_dir():
        raise ValueError("Repository path must be a directory")
    log = log_path.expanduser().resolve()
    if not log.is_file():
        raise ValueError("Log file must exist")

    initial_state = {
        "run_id": str(uuid.uuid4()),
        "target_path": str(repo),
        "log_path": str(log),
        "findings": [],
        "graph_metadata": {},
        "status": "INITIALIZED",
    }
    graph = build_devops_graph(skip_test_execution=True)
    return graph.invoke(initial_state)


st.title("DevOpsMind AI")
st.caption("Local-first software engineering and CI/CD intelligence")

if not Path(settings.DB_PATH).is_file():
    st.warning(f"Database not found: {settings.DB_PATH}. Run your existing initialization/analysis first.")

runs, findings = load_data()
latest = runs.iloc[0] if not runs.empty else None
latest_findings = findings[findings["run_id"] == latest["run_id"]] if latest is not None and not findings.empty else pd.DataFrame()

overview, explorer, history, new_run = st.tabs(["Overview", "Findings Explorer", "Analysis History", "New Analysis"])

with overview:
    if latest is None:
        st.info("No analysis runs recorded yet.")
    else:
        a, b, c, d = st.columns(4)
        a.metric("Latest project", str(latest["project_name"]))
        b.metric("Run status", str(latest["status"]))
        c.metric("Findings in latest run", len(latest_findings))
        d.metric("Run timestamp", str(latest["timestamp"]))
        left, right = st.columns(2)
        with left:
            score = pd.to_numeric(pd.Series([latest["health_score"]]), errors="coerce").iloc[0]
            if pd.notna(score) and 0 <= score <= 100:
                st.plotly_chart(health_gauge(score), width="stretch")
                st.caption("Value loaded from SQLite. Scoring methodology must be validated separately.")
            else:
                st.info("No valid recorded health score for this run.")
        with right:
            st.subheader("Findings by severity")
            if latest_findings.empty:
                st.info("No findings stored for the latest run.")
            else:
                counts = latest_findings["severity"].value_counts().reindex(SEVERITIES, fill_value=0)
                st.bar_chart(counts)
        if not latest_findings.empty:
            st.subheader("Findings by agent")
            st.bar_chart(latest_findings["agent_name"].value_counts())

with explorer:
    st.subheader("Consolidated findings")
    if findings.empty:
        st.info("No findings recorded.")
    else:
        f1, f2, f3 = st.columns(3)
        run_choices = runs["run_id"].tolist() if not runs.empty else findings["run_id"].dropna().unique().tolist()
        selected_run = f1.selectbox("Analysis run", ["All runs"] + run_choices)
        severity_choices = f2.multiselect("Severity", SEVERITIES, default=SEVERITIES)
        agent_choices = sorted(findings["agent_name"].dropna().unique().tolist())
        selected_agents = f3.multiselect("Agent", agent_choices, default=agent_choices)
        filtered = findings[findings["severity"].isin(severity_choices) & findings["agent_name"].isin(selected_agents)]
        if selected_run != "All runs":
            filtered = filtered[filtered["run_id"] == selected_run]
        st.caption(f"{len(filtered)} finding(s)")
        st.dataframe(filtered[["severity", "agent_name", "title", "file_path", "line_number", "timestamp"]],
                     width="stretch", hide_index=True)
        for _, item in filtered.head(100).iterrows():
            with st.expander(f"[{item['severity']}] {item['title']} â€” {item['agent_name']}"):
                st.write("**File:**", item["file_path"], "**Line:**", item["line_number"])
                st.write("**Description:**", item["description"])
                st.write("**Recommended fix:**", item["recommended_fix"] or "Not provided")
                st.caption(f"Run ID: {item['run_id']} | Finding ID: {item['finding_id']}")

with history:
    st.subheader("Analysis history")
    if runs.empty:
        st.info("No previous runs available.")
    else:
        st.dataframe(runs, width="stretch", hide_index=True)
        st.download_button("Export run history (CSV)", runs.to_csv(index=False),
                           file_name="devopsmind_run_history.csv", mime="text/csv")
        if not findings.empty:
            st.download_button("Export findings (CSV)", findings.to_csv(index=False),
                               file_name="devopsmind_findings.csv", mime="text/csv")

with new_run:
    st.subheader("Start repository analysis")
    st.warning("Generated-test execution is disabled until a real sandbox is configured. Other agent nodes will run.")
    repository = st.text_input("Local repository path", value=str(settings.BASE_DIR / "src"))
    log_file = st.text_input("Log file path", value=str(settings.BASE_DIR / "logs" / "build_error.log"))
    if st.button("Run analysis", type="primary"):
        if not repository.strip() or not log_file.strip():
            st.error("Both paths are required")
        else:
            try:
                with st.spinner("Running LangGraph analysis. Local Ollama calls may take time..."):
                    result = trigger_analysis(Path(repository), Path(log_file))
                st.success(f"Analysis finished. Run ID: {result['run_id']}; stored findings: {len(result['findings'])}")
                st.caption("Refresh results to display the newly persisted run.")
            except Exception as exc:
                st.error(f"Analysis failed: {type(exc).__name__}: {exc}")
    if st.button("Refresh database results"):
        st.rerun()

