"""
输入护栏：检测 Prompt 注入、恶意指令、超大输入、敏感文件等。
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GuardResult:
    """护栏检查结果"""

    allowed: bool
    reason: str = ""
    triggered_rules: List[str] = field(default_factory=list)


class InputGuard:
    """输入内容安全护栏"""

    # Prompt 注入常见特征词与模式
    INJECTION_PATTERNS = [
        r"忽略.{0,10}(提示|指令|prompt|instruction)",
        r"ignore\s+(the\s+)?(prompt|instruction|above|previous)",
        r"你是个?\s*.{0,20}(助手|AI|模型|model)",
        r"you\s+are\s+(not\s+)?an?\s+\w+",
        r"系统提示",
        r"system\s+prompt",
        r"不要.{0,10}(评估|打分|判断)",
        r"输出.{0,10}(代码|密码|密钥|key|token)",
        r"```\s*(system|yaml|json)",
    ]

    # 恶意指令模式
    MALICIOUS_PATTERNS = [
        r"删除.{0,10}(数据库|数据|文件)",
        r"drop\s+table",
        r"rm\s+-rf",
        r"exec\s*\(",
    ]

    MAX_INPUT_LENGTH = 10000
    MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, max_input_length: Optional[int] = None):
        self.max_input_length = max_input_length or self.MAX_INPUT_LENGTH

    def check(self, raw_inputs: List[Dict]) -> GuardResult:
        """检查输入列表（文本内容 + 附件）"""
        triggered = []

        total_length = 0
        for inp in raw_inputs:
            content = str(inp.get("content", ""))
            total_length += len(content)

            if total_length > self.max_input_length:
                return GuardResult(
                    allowed=False,
                    reason=f"输入总长度超过限制 {self.max_input_length} 字符",
                    triggered_rules=["input_size_limit"],
                )

            for pattern in self.INJECTION_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    triggered.append(f"injection_pattern:{pattern}")

            for pattern in self.MALICIOUS_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    triggered.append(f"malicious_pattern:{pattern}")

            # 校验附件类型与大小
            for att in inp.get("attachments", []) or []:
                att_result = self.check_attachment(
                    filename=att.get("filename", ""),
                    size=att.get("size", len(att.get("data", "")) if isinstance(att.get("data"), str) else 0),
                    mime=att.get("mime", ""),
                )
                if not att_result.allowed:
                    return att_result

        if triggered:
            return GuardResult(
                allowed=False,
                reason="检测到潜在 Prompt 注入或恶意指令",
                triggered_rules=triggered,
            )

        return GuardResult(allowed=True)

    def check_attachment(self, filename: str, size: int, mime: str) -> GuardResult:
        """检查附件"""
        allowed_exts = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".wav", ".mp3"}
        ext = filename.lower()[filename.rfind(".") :]
        if ext not in allowed_exts:
            return GuardResult(
                allowed=False,
                reason=f"不支持的附件类型: {ext}",
                triggered_rules=["unsupported_attachment_type"],
            )
        if size > self.MAX_ATTACHMENT_SIZE:
            return GuardResult(
                allowed=False,
                reason="附件大小超过 10MB 限制",
                triggered_rules=["attachment_size_limit"],
            )
        return GuardResult(allowed=True)
