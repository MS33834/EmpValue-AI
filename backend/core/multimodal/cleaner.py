"""
多模态清洗器：编排各抽取器，将原始输入中的附件统一转为文本。
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.multimodal.extractors import (
    AudioExtractor,
    BaseExtractor,
    ImageExtractor,
    PdfExtractor,
    TableExtractor,
    TextExtractor,
    UnknownExtractor,
    _detect_kind,
)

logger = logging.getLogger(__name__)


@dataclass
class CleanResult:
    """单条输入的清洗结果"""

    input_id: str
    cleaned_content: str
    extracted_attachments: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class MultimodalCleaner:
    """
    多模态清洗器。
    负责遍历 raw_inputs，对每条输入的 attachments 调用对应抽取器，
    将抽取出的文本拼接到输入 content 之后，形成 cleaned_content。
    """

    def __init__(
        self,
        vision_callable=None,
        asr_callable=None,
    ):
        self._extractors: Dict[str, BaseExtractor] = {
            "text": TextExtractor(),
            "table": TableExtractor(),
            "image": ImageExtractor(vision_callable=vision_callable),
            "audio": AudioExtractor(asr_callable=asr_callable),
            "pdf": PdfExtractor(),
            "unknown": UnknownExtractor(),
        }

    def register_extractor(self, kind: str, extractor: BaseExtractor) -> None:
        """注册/覆盖某种类型的抽取器"""
        self._extractors[kind] = extractor

    async def clean_inputs(
        self, raw_inputs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        清洗整批输入，返回 enriched inputs：
        每条输入新增 extracted_text 字段（附件抽取汇总），content 保持不变。
        """
        cleaned: List[Dict[str, Any]] = []
        for inp in raw_inputs:
            enriched = dict(inp)
            attachments = inp.get("attachments") or []
            if not attachments:
                cleaned.append(enriched)
                continue

            extracted_parts: List[str] = []
            for att in attachments:
                kind = _detect_kind(att.get("mime", ""), att.get("filename", ""))
                extractor = self._extractors.get(kind) or self._extractors["unknown"]
                try:
                    text = await extractor.extract(att)
                    extracted_parts.append(text)
                except Exception as e:
                    logger.exception("附件抽取异常")
                    extracted_parts.append(
                        f"[附件 {att.get('filename', '?')}] 抽取异常: {e}"
                    )

            enriched["extracted_text"] = "\n\n".join(extracted_parts)
            # 合并到 content 末尾，便于 LLM 直接消费
            base_content = inp.get("content", "") or ""
            if extracted_parts:
                enriched["content"] = (
                    f"{base_content}\n\n--- 附件抽取内容 ---\n"
                    + "\n\n".join(extracted_parts)
                ).strip()
            cleaned.append(enriched)
        return cleaned

    async def clean_single(self, raw_input: Dict[str, Any]) -> CleanResult:
        """清洗单条输入，返回详细结果（用于调试/审计）"""
        input_id = raw_input.get("input_id", "unknown")
        attachments = raw_input.get("attachments") or []
        extracted: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []

        for att in attachments:
            kind = _detect_kind(att.get("mime", ""), att.get("filename", ""))
            extractor = self._extractors.get(kind) or self._extractors["unknown"]
            try:
                text = await extractor.extract(att)
                extracted.append(text)
            except Exception as e:
                errors.append(f"{att.get('filename', '?')}: {e}")

        base = raw_input.get("content", "") or ""
        if extracted:
            cleaned_content = (
                f"{base}\n\n--- 附件抽取内容 ---\n" + "\n\n".join(extracted)
            ).strip()
        else:
            cleaned_content = base

        return CleanResult(
            input_id=input_id,
            cleaned_content=cleaned_content,
            extracted_attachments=extracted,
            skipped=skipped,
            errors=errors,
        )
