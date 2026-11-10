import re
import uuid
from pathlib import Path
from typing import List, Dict, Any
from langchain_ollama import OllamaLLM
from src.devopsmind.config import settings
from src.devopsmind.schemas.findings import Finding

class LogAnalysisAgent:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.agent_name = "LogAnalysisAgent"
        self.llm = OllamaLLM(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL
        )

    def parse_log_file(self, log_file_path: str) -> List[Dict[str, Any]]:
        """Parses raw build, test, or deployment logs for stack traces and errors."""
        path = Path(log_file_path)
        if not path.exists():
            return []

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        errors = []
        # Match common Python traceback or error patterns
        traceback_pattern = re.compile(r'(Traceback \(most recent call last\):[\s\S]*?\n\w+Error: .+)', re.MULTILINE)
        matches = traceback_pattern.findall(content)

        if matches:
            for match in matches:
                errors.append({
                    "type": "Python Traceback",
                    "snippet": match.strip()[:1000],
                    "line_number": 1
                })
        else:
            # Fallback: scan for general error / failed lines
            for line_no, line in enumerate(content.splitlines(), start=1):
                if any(keyword in line.lower() for keyword in ["error", "fail", "exception", "fatal"]):
                    errors.append({
                        "type": "Log Error Line",
                        "snippet": line.strip(),
                        "line_number": line_no
                    })

        return errors[:5]  # Limit to top 5 errors

    def analyze(self, log_file_path: str) -> List[Finding]:
        print(f"[{self.agent_name}] Analyzing log file: {log_file_path}...")
        raw_errors = self.parse_log_file(log_file_path)
        print(f"[{self.agent_name}] Detected {len(raw_errors)} error signatures in logs.")

        findings: List[Finding] = []

        for err in raw_errors:
            snippet = err["snippet"]
            line_no = err["line_number"]

            prompt = f"""You are a DevOps Incident Response and Log Troubleshooting Expert.
Analyze this error trace extracted from build/test logs:
{snippet}

Provide a 2-sentence root cause explanation and a recommended operational fix.
"""
            try:
                explanation = self.llm.invoke(prompt).strip()
            except Exception as e:
                explanation = f"Log anomaly detected: {err['type']}. (LLM diagnosis unavailable: {e})"

            finding = Finding(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                agent_name=self.agent_name,
                severity="HIGH",
                file_path=log_file_path,
                line_number=line_no,
                title=f"[LOG_ERROR] {err['type']} detected",
                description=explanation,
                recommended_fix="Review build configuration or correct failing test/runtime parameters."
            )
            findings.append(finding)

        return findings