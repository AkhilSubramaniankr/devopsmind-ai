"""One-time safe change to existing LangGraph workflow; makes a backup."""
from pathlib import Path
import shutil

path = Path("src/devopsmind/orchestration/graph.py")
if not path.is_file():
    raise SystemExit(f"Missing {path}; run from project root")
original = path.read_text(encoding="utf-8")
if "skip_test_execution" in original:
    raise SystemExit("Already patched; inspect graph.py before continuing")
old_sig = "def build_devops_graph() -> StateGraph:"
old_edge = '    workflow.add_edge("architecture", "test_gen")'
if original.count(old_sig) != 1 or original.count(old_edge) != 1:
    raise SystemExit("Unexpected graph.py version; no changes made")
updated = original.replace(old_sig, "def build_devops_graph(skip_test_execution: bool = True):")
updated = updated.replace('    workflow.add_node("test_gen", run_test_gen_node)', '    if not skip_test_execution:\n        workflow.add_node("test_gen", run_test_gen_node)')
updated = updated.replace('    workflow.add_edge("test_gen", "log_analysis")', '    if not skip_test_execution:\n        workflow.add_edge("test_gen", "log_analysis")')
updated = updated.replace(old_edge, "    if skip_test_execution:\n        workflow.add_edge('architecture', 'log_analysis')\n    else:\n        workflow.add_edge('architecture', 'test_gen')")
# Test node and its outgoing edge are excluded entirely in safe mode.
backup = path.with_suffix(".py.bak")
if backup.exists():
    raise SystemExit(f"Backup already exists: {backup}; no changes made")
shutil.copy2(path, backup)
path.write_text(updated, encoding="utf-8")
print(f"Patched {path}; backup: {backup}")
print("Default workflow skips unsafe generated test execution.")
