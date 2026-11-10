import os
import ast
import uuid
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from langchain_ollama import OllamaLLM
from src.devopsmind.config import settings
from src.devopsmind.schemas.findings import Finding

class TestGenerationAgent:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agent_name = "TestGenerationAgent"
        self.llm = OllamaLLM(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL
        )
        self.sandbox_dir = settings.BASE_DIR / "data" / "sandbox_tests"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def extract_target_functions(self, target_path: str) -> List[Dict[str, Any]]:
        """Scans Python files and extracts top-level functions for test generation."""
        functions = []
        base_dir = Path(target_path).resolve()
        
        for py_file in base_dir.glob("**/*.py"):
            # Skip test files themselves
            if "test_" in py_file.name:
                continue
            try:
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    tree = ast.parse(content, filename=str(py_file))
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Extract source code snippet of the function
                        lines = content.splitlines()
                        func_code = "\n".join(lines[node.lineno - 1 : node.end_lineno]) if hasattr(node, 'end_lineno') else f"def {node.name}(): pass"
                        
                        functions.append({
                            "name": node.name,
                            "file_path": str(py_file),
                            "code_snippet": func_code
                        })
            except Exception as e:
                print(f"[{self.agent_name}] Error extracting functions from {py_file}: {e}")
                
        return functions[:3]  # Limit to 3 functions per run to keep execution fast

    def generate_and_execute_tests(self, target_path: str) -> List[Finding]:
        print(f"[{self.agent_name}] Inspecting functions for automated test generation...")
        target_funcs = self.extract_target_functions(target_path)
        print(f"[{self.agent_name}] Selected {len(target_funcs)} functions for testing.")

        findings: List[Finding] = []

        for func in target_funcs:
            func_name = func["name"]
            func_code = func["code_snippet"]
            file_path = func["file_path"]

            print(f"[{self.agent_name}] Generating PyTest cases for function '{func_name}'...")

            prompt = f"""You are an Expert QA and Test Automation Engineer.
Write a complete, executable PyTest test file in Python for the following function.
Return ONLY valid Python code block using ```python ... ``` without extra conversational text.

Target Function Code:
{func_code}
"""
            try:
                response = self.llm.invoke(prompt).strip()
                # Extract python code block
                if "```python" in response:
                    test_code = response.split("```python")[1].split("```")[0].strip()
                elif "```" in response:
                    test_code = response.split("```")[1].split("```")[0].strip()
                else:
                    test_code = response

                # Save generated test into sandbox
                test_file_name = f"test_{func_name}_{uuid.uuid4().hex[:6]}.py"
                test_file_path = self.sandbox_dir / test_file_name
                with open(test_file_path, "w", encoding="utf-8") as tf:
                    tf.write(test_code)

                # Execute pytest in isolated sandbox with timeout limit
                print(f"[{self.agent_name}] Executing generated test: {test_file_name}")
                result = subprocess.run(
                    ["pytest", str(test_file_path), "--no-header", "-v"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False
                )

                passed = result.returncode == 0
                output_log = result.stdout + result.stderr

                if not passed:
                    finding = Finding(
                        id=str(uuid.uuid4()),
                        run_id=self.run_id,
                        agent_name=self.agent_name,
                        severity="MEDIUM",
                        file_path=file_path,
                        line_number=1,
                        title=f"[TEST_FAILURE] Generated test failed for '{func_name}'",
                        description=f"Automated test execution failed.\nPyTest Output:\n{output_log[:500]}",
                        recommended_fix="Review function implementation or adjust boundary assertions in generated test."
                    )
                    findings.append(finding)
                else:
                    print(f"[{self.agent_name}] Test passed successfully for '{func_name}'!")

            except subprocess.TimeoutExpired:
                print(f"[{self.agent_name}] Test execution timed out for {func_name}.")
            except Exception as e:
                print(f"[{self.agent_name}] Error during test generation/execution: {e}")

        return findings