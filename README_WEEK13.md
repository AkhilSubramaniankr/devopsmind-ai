# DevOpsMind AI — Week 13 dashboard integration

1. Back up your project, including `data/devopsmind.db`.
2. Copy `src/devopsmind/ui/app.py` into the matching location in your project.
3. Review and run `python scripts/enable_safe_dashboard_graph.py` from the project root. It backs up the original `graph.py` before patching it. The patched graph defaults to skipping generated test execution, including CLI runs.
4. Run `python -m streamlit run src/devopsmind/ui/app.py` from the project root.

## Important caveats

- The dashboard runs the provided LangGraph workflow synchronously; local Ollama may take time.
- The existing graph marks the run `COMPLETED` even though the test node is skipped. This is a workflow completion status, not evidence all tests passed.
- The stored health score is hardcoded to 85 by the existing graph and should not be treated as a computed metric.
- The dashboard analyzes a user-supplied local directory. Only use trusted local repositories; this patch does not harden ZIP extraction, prompt injection, or the other agents' subprocess handling.
- Do not enable generated-test execution (`skip_test_execution=False`) for untrusted content without a genuine isolated runner.
- Existing database schema is unchanged.
