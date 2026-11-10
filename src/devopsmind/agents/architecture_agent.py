import ast
import uuid
import networkx as nx
from pathlib import Path
from typing import List, Dict, Any, Tuple
from langchain_ollama import OllamaLLM
from src.devopsmind.config import settings
from src.devopsmind.schemas.findings import Finding

class ArchitectureAgent:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agent_name = "ArchitectureAgent"
        self.llm = OllamaLLM(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL
        )

    def build_dependency_graph(self, target_path: str) -> Tuple[nx.DiGraph, List[Dict[str, Any]]]:
        """Scans Python files and constructs a directed module dependency graph."""
        graph = nx.DiGraph()
        base_dir = Path(target_path).resolve()
        py_files = list(base_dir.glob("**/*.py"))

        module_stats = []

        for py_file in py_files:
            rel_module = py_file.relative_to(base_dir).with_suffix("").as_posix().replace("/", ".")
            graph.add_node(rel_module)

            try:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    tree = ast.parse(content, filename=str(py_file))
                    line_count = len(content.splitlines())

                imports_count = 0
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports_count += 1
                        if isinstance(node, ast.ImportFrom) and node.module:
                            graph.add_edge(rel_module, node.module)
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                graph.add_edge(rel_module, alias.name)

                module_stats.append({
                    "module": rel_module,
                    "file_path": str(py_file),
                    "line_count": line_count,
                    "imports_count": imports_count
                })

            except Exception as e:
                print(f"[{self.agent_name}] Warning: Could not parse {py_file} for AST: {e}")

        return graph, module_stats

    def analyze(self, target_path: str) -> Tuple[List[Finding], Dict[str, Any]]:
        print(f"[{self.agent_name}] Extracting dependency graph for {target_path}...")
        graph, module_stats = self.build_dependency_graph(target_path)

        findings: List[Finding] = []

        # 1. Detect Circular Dependencies using NetworkX
        cycles = list(nx.simple_cycles(graph))
        print(f"[{self.agent_name}] Total modules: {len(graph.nodes)}, Circular cycles detected: {len(cycles)}")

        for cycle in cycles:
            cycle_str = " -> ".join(cycle) + f" -> {cycle[0]}"
            prompt = f"Explain why circular module dependencies like '{cycle_str}' degrade software maintainability in 2 sentences."
            try:
                explanation = self.llm.invoke(prompt).strip()
            except Exception:
                explanation = "Circular import detected. This can cause runtime import errors and high coupling."

            finding = Finding(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                agent_name=self.agent_name,
                severity="HIGH",
                file_path=cycle[0],
                line_number=1,
                title="[CIRCULAR_DEPENDENCY] Module import loop detected",
                description=f"Circular cycle: {cycle_str}. {explanation}",
                recommended_fix="Refactor shared components into a common utility module to break the cycle."
            )
            findings.append(finding)

        # 2. Detect Overly Complex / Large Files (>150 lines)
        for stat in module_stats:
            if stat["line_count"] > 150:
                finding = Finding(
                    id=str(uuid.uuid4()),
                    run_id=self.run_id,
                    agent_name=self.agent_name,
                    severity="MEDIUM",
                    file_path=stat["file_path"],
                    line_number=1,
                    title="[HIGH_COMPLEXITY] Large file detected",
                    description=f"Module '{stat['module']}' contains {stat['line_count']} lines. Consider splitting into sub-modules.",
                    recommended_fix="Decompose functions and classes into separate, single-responsibility files."
                )
                findings.append(finding)

        graph_summary = {
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "cycles_count": len(cycles)
        }

        return findings, graph_summary