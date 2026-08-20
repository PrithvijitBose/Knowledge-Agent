import os
import time
from typing import Dict, Any, List


class ExecutionTracer:
    """Records execution metrics, latencies, and writes formatted GitHub Step Summaries."""

    def __init__(self, owner: str, repo: str, issue_number: int, author: str):
        self._time = time
        self.owner = owner
        self.repo = repo
        self.issue_number = issue_number
        self.author = author
        self.start_time = time.time()
        self.intent: str = "UNKNOWN"
        self.files_read: List[str] = []
        self.engine: str = "Unknown"
        self.success: bool = False

    def finish(self, success: bool, result: Dict[str, Any]):
        self.success = success
        self.intent = result.get("intent", self.intent)
        self.files_read = result.get("files_read", self.files_read)
        self.engine = result.get("engine", self.engine)
        self.write_step_summary()

    def generate_markdown_summary(self) -> str:
        total_time = round(self._time.time() - self.start_time, 2)
        status_badge = "✅ **Success**" if self.success else "❌ **Failed**"

        md = [
            f"## 🧠 Knowledge Agent Execution Summary",
            f"",
            f"| Metric | Value |",
            f"| :--- | :--- |",
            f"| **Target** | `{self.owner}/{self.repo}#{self.issue_number}` |",
            f"| **Trigger Author** | `@{self.author}` |",
            f"| **Status** | {status_badge} |",
            f"| **Detected Intent** | `{self.intent}` |",
            f"| **AI Engine** | `{self.engine}` |",
            f"| **Total Elapsed Time** | `{total_time}s` |",
            f"| **Evidence Files Read** | `{len(self.files_read)} files` |",
            f"",
        ]
        if self.files_read:
            md.append("### 📁 Evaluated Files")
            for f in sorted(self.files_read):
                md.append(f"- `{f}`")
            md.append("")

        return "\n".join(md)

    def write_step_summary(self):
        summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if not summary_path:
            return
        try:
            content = self.generate_markdown_summary()
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(content + "\n")
        except Exception as e:
            print(f"Failed to write GITHUB_STEP_SUMMARY: {e}")
