import subprocess
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
from langchain_ollama import OllamaLLM
from src.devopsmind.config import settings
from src.devopsmind.schemas.findings import Finding

def run_ruff_linter(target_path: str) -> List[Dict[str, Any]]:
    """Runs ruff check in JSON mode over the target path."""
    try:
        result = subprocess.run(
            ["ruff", "check", target_path, "--output-format=json"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return []
    except Exception as e:
        print(f"[CodeReviewAgent] Ruff linter execution error: {e}")
        return []

class CodeReviewAgent:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agent_name = "CodeReviewAgent"
        self.llm = OllamaLLM(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL
        )

    def analyze(self, target_path: str) -> List[Finding]:
        print(f"[{self.agent_name}] Running Ruff static check on {target_path}...")
        raw_issues = run_ruff_linter(target_path)
        print(f"[{self.agent_name}] Detected {len(raw_issues)} static issues.")

        findings: List[Finding] = []

        # Process up to the top 5 issues to keep local LLM execution fast
        for issue in raw_issues[:5]:
            file_path = issue.get("filename", "")
            line_no = issue.get("location", {}).get("row", 1)
            code = issue.get("code", "QUALITY_ISSUE")
            message = issue.get("message", "Potential code quality problem detected.")

            # Severity mapping based on Ruff codes
            severity = "MEDIUM"
            if code.startswith("E") or code.startswith("F"):  # Syntax Errors / PyFlakes
                severity = "HIGH"
            elif code.startswith("I") or code.startswith("D"): # Imports / Docs
                severity = "LOW"

            # Prompt LLM for explanation and suggested fix
            prompt = f"""You are a Code Quality and Review Expert.
Analyze this linter finding:
- File: {file_path}
- Line: {line_no}
- Rule Code: {code}
- Message: {message}

Provide a concise 2-sentence explanation of why this is a code smell or bug, and supply the corrected Python code snippet.
"""
            try:
                explanation = self.llm.invoke(prompt).strip()
            except Exception as e:
                explanation = f"Linter rule violation: {message}. (LLM explanation unavailable: {e})"

            finding = Finding(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                agent_name=self.agent_name,
                severity=severity,
                file_path=file_path,
                line_number=line_no,
                title=f"[{code}] {message}",
                description=explanation,
                recommended_fix=f"Review line {line_no} for rule violation {code}."
            )
            findings.append(finding)

        return findings