import subprocess
import json
import uuid
import re
from pathlib import Path 
from typing import List, Dict, Any
from langchain_ollama import OllamaLLM
from src.devopsmind.config import settings
from src.devopsmind.schemas.findings import Finding

def run_bandit_scanner(target_path: str) -> List[Dict[str, Any]]:
    """Runs Bandit security scanner in JSON mode over the target path."""
    try:
        result = subprocess.run(
            ["bandit", "-r", target_path, "-f", "json"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.stdout.strip():
            data = json.loads(result.stdout)
            return data.get("results", [])
        return []
    except Exception as e:
        print(f"[SecurityAgent] Bandit scanner execution error: {e}")
        return []

def scan_for_basic_secrets(target_path: str) -> List[Dict[str, Any]]:
    """Simple regex secret scanner fallback if Gitleaks is not installed."""
    secret_patterns = {
        "AWS API Key": r"AKIA[0-9A-Z]{16}",
        "Generic Secret/Token": r"(?i)(api_key|secret_key|password|token)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]",
    }
    findings = []
    path = Path(target_path)
    if not path.exists():
        return findings

    for py_file in path.glob("**/*.py"):
        try:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                for line_no, line in enumerate(f, start=1):
                    for label, pattern in secret_patterns.items():
                        if re.search(pattern, line):
                            # Redact line snippet
                            redacted_line = re.sub(r"=['\"].*?['\"]", "='[REDACTED]'", line.strip())
                            findings.append({
                                "filename": str(py_file),
                                "line_number": line_no,
                                "issue_text": f"Potential {label} detected",
                                "code_snippet": redacted_line,
                                "severity": "CRITICAL"
                            })
        except Exception:
            continue
    return findings

class SecurityAgent:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agent_name = "SecurityAgent"
        self.llm = OllamaLLM(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL
        )

    def analyze(self, target_path: str) -> List[Finding]:
        print(f"[{self.agent_name}] Running Bandit SAST scan on {target_path}...")
        bandit_results = run_bandit_scanner(target_path)
        secret_results = scan_for_basic_secrets(target_path)

        print(f"[{self.agent_name}] Detected {len(bandit_results)} SAST issues and {len(secret_results)} potential secrets.")

        findings: List[Finding] = []

        # 1. Process Secret Detections
        for secret in secret_results:
            finding = Finding(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                agent_name=self.agent_name,
                severity="CRITICAL",
                file_path=secret["filename"],
                line_number=secret["line_number"],
                title=f"[SECRET_LEAK] {secret['issue_text']}",
                description=f"Hardcoded credential risk: {secret['code_snippet']}. Remove credentials and store in environment variables.",
                recommended_fix="Use environment variables or a secrets vault instead of hardcoding sensitive strings."
            )
            findings.append(finding)

        # 2. Process Bandit SAST Findings (up to top 5)
        for issue in bandit_results[:5]:
            file_path = issue.get("filename", "")
            line_no = issue.get("line_number", 1)
            test_id = issue.get("test_id", "SECURITY_ISSUE")
            severity_raw = issue.get("issue_severity", "MEDIUM").upper()
            issue_text = issue.get("issue_text", "Potential security flaw.")

            severity = "HIGH" if severity_raw == "HIGH" else "MEDIUM"

            prompt = f"""You are an Application Security Expert.
Analyze this Bandit SAST finding:
- File: {file_path}
- Line: {line_no}
- Vulnerability ID: {test_id}
- Description: {issue_text}

Explain the risk in 2 simple sentences and provide a secure coding recommendation.
"""
            try:
                explanation = self.llm.invoke(prompt).strip()
            except Exception as e:
                explanation = f"Security risk: {issue_text}. (LLM explanation unavailable: {e})"

            finding = Finding(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                agent_name=self.agent_name,
                severity=severity,
                file_path=file_path,
                line_number=line_no,
                title=f"[{test_id}] {issue_text}",
                description=explanation,
                recommended_fix=f"Review security flaw at line {line_no} and apply sanitized input or secure patterns."
            )
            findings.append(finding)

        return findings