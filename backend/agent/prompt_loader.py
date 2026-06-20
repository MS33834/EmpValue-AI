"""
Prompt 加载与渲染工具
使用正则表达式精确替换占位符，避免 Prompt 中的 JSON 示例被误解析。
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List


class PromptLoader:
    """加载 Prompt 文件并替换变量"""

    PLACEHOLDERS = [
        "raw_inputs",
        "employee_history",
        "company_kb",
        "employee_id",
        "period",
    ]

    def __init__(self, prompts_dir: Path = None):
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent.parent / "prompts"
        self.prompts_dir = prompts_dir

    def load(self, name: str) -> str:
        path = self.prompts_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {path}")
        return path.read_text(encoding="utf-8")

    def version(self, name: str) -> str:
        """从 Prompt 文件头提取版本号"""
        text = self.load(name)
        for line in text.splitlines()[:10]:
            if "版本" in line and "v" in line:
                match = re.search(r"v\d+\.\d+", line)
                if match:
                    return match.group(0)
        return "unknown"

    def render(
        self,
        name: str,
        raw_inputs: List[Dict[str, Any]],
        employee_history: List[Dict[str, Any]] = None,
        company_kb: List[Dict[str, Any]] = None,
        employee_id: str = "",
        period: str = "",
    ) -> str:
        """渲染 Prompt，替换占位符"""
        template = self.load(name)
        values = {
            "raw_inputs": json.dumps(raw_inputs, ensure_ascii=False, indent=2),
            "employee_history": json.dumps(employee_history or [], ensure_ascii=False, indent=2),
            "company_kb": json.dumps(company_kb or [], ensure_ascii=False, indent=2),
            "employee_id": employee_id,
            "period": period,
        }

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            return values.get(key, match.group(0))

        # 仅替换 {raw_inputs} 等已知占位符，保留其他花括号
        pattern = re.compile(r"\{(" + "|".join(self.PLACEHOLDERS) + r")\}")
        return pattern.sub(replacer, template)
