"""
输出护栏：PII 脱敏、歧视/偏见检测、员工视图负面词过滤。
"""

import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class OutputGuardResult:
    """输出护栏结果"""

    clean_text: str
    violations: List[str]
    redacted_entities: List[str]


class OutputGuard:
    """输出内容安全护栏"""

    # 员工视图禁用负面词（避免误命中“差距”“信息差”等中性复合词）
    NEGATIVE_WORDS = [
        "很差", "太差", "较差", "差劲", "表现差", "态度差", "质量差", "能力差", "水平差",
        "懒", "慢", "拖沓", "消极", "不合格", "无能", "没用",
        "糟糕", "失败", "失职", "敷衍", "逃避", "推卸", "废柴", "混日子",
    ]

    # PII 模式（简化版）
    PII_PATTERNS = [
        (r"\b1[3-9]\d{9}\b", "手机号"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "邮箱"),
        (r"\b\d{17}[\dXx]\b", "身份证号"),
        (r"\b\d{4}[-/]?\d{2}[-/]?\d{2}\b", "日期"),
    ]

    # 歧视/偏见敏感词
    BIASED_WORDS = [
        "性别", "年龄", "籍贯", "星座", "血型", "属相", "生肖",
        "剩女", "大龄", "外地", "农村", "乡下",
    ]

    def redact_pii(self, text: str) -> tuple[str, List[str]]:
        """对文本中的 PII 进行脱敏"""
        redacted = []
        result = text
        for pattern, label in self.PII_PATTERNS:
            matches = re.findall(pattern, result)
            for m in matches:
                redacted.append(f"{label}:{m}")
            result = re.sub(pattern, f"[{label}已脱敏]", result)
        return result, redacted

    def check_negative_words(self, text: str) -> List[str]:
        """检查员工视图是否包含负面词"""
        return [w for w in self.NEGATIVE_WORDS if w in text]

    def check_bias(self, text: str) -> List[str]:
        """检查是否存在偏见表述"""
        return [w for w in self.BIASED_WORDS if w in text]

    def sanitize_employee_view(self, employee_view: Dict) -> OutputGuardResult:
        """对员工视图进行安全处理"""
        violations = []
        redacted_all = []

        text_fields = ["summary", "strengths"]
        for field in text_fields:
            value = employee_view.get(field, "")
            if isinstance(value, list):
                cleaned = []
                for item in value:
                    c, r = self.redact_pii(item)
                    cleaned.append(c)
                    redacted_all.extend(r)
                employee_view[field] = cleaned
            elif isinstance(value, str):
                cleaned, r = self.redact_pii(value)
                employee_view[field] = cleaned
                redacted_all.extend(r)

        # 检查成长维度
        for area in employee_view.get("growth_areas", []):
            for key in ["evidence", "improvement_actions"]:
                value = area.get(key, [])
                cleaned = []
                for item in value:
                    c, r = self.redact_pii(item)
                    cleaned.append(c)
                    redacted_all.extend(r)
                area[key] = cleaned

        # 负面词检查
        view_text = str(employee_view)
        negatives = self.check_negative_words(view_text)
        if negatives:
            violations.append(f"employee_view_negative_words:{','.join(negatives)}")

        # 偏见检查
        biased = self.check_bias(view_text)
        if biased:
            violations.append(f"biased_words:{','.join(biased)}")

        return OutputGuardResult(
            clean_text=str(employee_view),
            violations=violations,
            redacted_entities=redacted_all,
        )

    def sanitize_manager_view(self, manager_view: Dict) -> OutputGuardResult:
        """对管理视图进行 PII 脱敏（允许尖锐判断，但脱敏敏感信息）"""
        redacted_all = []
        text = str(manager_view)
        cleaned, redacted = self.redact_pii(text)
        redacted_all.extend(redacted)

        # 反序列化（简化处理，实际应递归处理每个字段）
        # 这里仅返回脱敏后的文本表示，实际生产环境应递归处理 dict
        return OutputGuardResult(
            clean_text=cleaned,
            violations=[],
            redacted_entities=redacted_all,
        )
