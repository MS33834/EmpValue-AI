"""
多模态数据清洗模块测试
"""

import base64

import pytest

from core.multimodal import MultimodalCleaner
from core.multimodal.extractors import (
    AudioExtractor,
    ImageExtractor,
    TableExtractor,
    TextExtractor,
    UnknownExtractor,
    _detect_kind,
)


def test_detect_kind():
    assert _detect_kind("image/png", "screenshot.png") == "image"
    assert _detect_kind("audio/wav", "voice.wav") == "audio"
    assert _detect_kind("text/csv", "data.csv") == "table"
    assert _detect_kind("text/plain", "notes.txt") == "text"
    assert _detect_kind("application/pdf", "report.pdf") == "pdf"
    assert _detect_kind("", "file.xyz") == "unknown"


@pytest.mark.asyncio
async def test_text_extractor_with_content():
    ext = TextExtractor()
    att = {"filename": "notes.txt", "content": "今日完成需求评审"}
    result = await ext.extract(att)
    assert "今日完成需求评审" in result
    assert "notes.txt" in result


@pytest.mark.asyncio
async def test_text_extractor_with_base64():
    ext = TextExtractor()
    raw = "周报内容".encode("utf-8")
    att = {"filename": "weekly.md", "data": base64.b64encode(raw).decode()}
    result = await ext.extract(att)
    assert "周报内容" in result


@pytest.mark.asyncio
async def test_table_extractor_csv():
    ext = TableExtractor()
    csv_bytes = "name,score,task\n张三,90,登录模块\n李四,85,接口联调\n".encode("utf-8")
    att = {"filename": "scores.csv", "data": base64.b64encode(csv_bytes).decode()}
    result = await ext.extract(att)
    assert "name" in result
    assert "张三" in result
    assert "李四" in result
    assert "|" in result  # markdown 表格


@pytest.mark.asyncio
async def test_table_extractor_truncation():
    """超长表格应被截断"""
    ext = TableExtractor()
    rows = [f"row{i},{i}\n" for i in range(100)]
    csv_bytes = "header1,header2\n" + "".join(rows)
    att = {"filename": "big.csv", "data": base64.b64encode(csv_bytes.encode()).decode()}
    result = await ext.extract(att)
    assert "已截断" in result


@pytest.mark.asyncio
async def test_image_extractor_without_vision():
    """未配置 vision 时应优雅降级"""
    ext = ImageExtractor()
    att = {"filename": "screenshot.png", "data": base64.b64encode(b"fakepng").decode()}
    result = await ext.extract(att)
    assert "未配置" in result
    assert "screenshot.png" in result


@pytest.mark.asyncio
async def test_image_extractor_with_vision():
    """配置 vision callable 后应调用"""

    async def fake_vision(b64, mime, filename):
        return f"图片描述：{filename} 包含一个登录界面"

    ext = ImageExtractor(vision_callable=fake_vision)
    att = {
        "filename": "ui.png",
        "mime": "image/png",
        "data": base64.b64encode(b"fakepng").decode(),
    }
    result = await ext.extract(att)
    assert "登录界面" in result
    assert "ui.png" in result


@pytest.mark.asyncio
async def test_audio_extractor_without_asr():
    ext = AudioExtractor()
    att = {"filename": "voice.mp3", "data": base64.b64encode(b"fakeaudio").decode()}
    result = await ext.extract(att)
    assert "未配置" in result


@pytest.mark.asyncio
async def test_audio_extractor_with_asr():

    async def fake_asr(payload, filename):
        return "今日完成了三个任务"

    ext = AudioExtractor(asr_callable=fake_asr)
    att = {"filename": "voice.mp3", "data": base64.b64encode(b"fakeaudio").decode()}
    result = await ext.extract(att)
    assert "今日完成了三个任务" in result


@pytest.mark.asyncio
async def test_unknown_extractor():
    ext = UnknownExtractor()
    att = {"filename": "data.bin", "mime": "application/octet-stream"}
    result = await ext.extract(att)
    assert "不支持" in result


@pytest.mark.asyncio
async def test_cleaner_no_attachments():
    """无附件的输入应原样返回"""
    cleaner = MultimodalCleaner()
    inputs = [{"input_id": "i1", "content": "纯文本日报", "attachments": []}]
    result = await cleaner.clean_inputs(inputs)
    assert len(result) == 1
    assert result[0]["content"] == "纯文本日报"
    assert "extracted_text" not in result[0]


@pytest.mark.asyncio
async def test_cleaner_mixed_attachments():
    """混合附件应分别抽取并合并到 content"""
    cleaner = MultimodalCleaner()
    csv_bytes = "name,score\n张三,90\n".encode("utf-8")
    inputs = [
        {
            "input_id": "i1",
            "content": "本周工作汇报",
            "attachments": [
                {"filename": "scores.csv", "data": base64.b64encode(csv_bytes).decode()},
                {"filename": "screenshot.png", "data": base64.b64encode(b"fake").decode()},
                {"filename": "voice.mp3", "data": base64.b64encode(b"fake").decode()},
            ],
        }
    ]
    result = await cleaner.clean_inputs(inputs)
    assert len(result) == 1
    content = result[0]["content"]
    assert "本周工作汇报" in content
    assert "附件抽取内容" in content
    assert "张三" in content  # CSV 抽取
    assert "未配置" in content  # 图片/音频降级说明
    assert "extracted_text" in result[0]


@pytest.mark.asyncio
async def test_cleaner_extract_exception_does_not_crash():
    """单个附件抽取异常不应中断整体清洗"""

    async def boom_vision(b64, mime, filename):
        raise RuntimeError("vision service down")

    cleaner = MultimodalCleaner(vision_callable=boom_vision)
    inputs = [
        {
            "input_id": "i1",
            "content": "日报",
            "attachments": [
                {"filename": "img.png", "data": base64.b64encode(b"fake").decode()},
            ],
        }
    ]
    result = await cleaner.clean_inputs(inputs)
    assert len(result) == 1
    # 异常被捕获，content 中应包含失败说明
    assert "抽取失败" in result[0]["content"] or "未配置" in result[0]["content"]


@pytest.mark.asyncio
async def test_clean_single_returns_detail():
    cleaner = MultimodalCleaner()
    csv_bytes = "a,b\n1,2\n".encode("utf-8")
    raw = {
        "input_id": "i1",
        "content": "日报",
        "attachments": [{"filename": "d.csv", "data": base64.b64encode(csv_bytes).decode()}],
    }
    result = await cleaner.clean_single(raw)
    assert result.input_id == "i1"
    assert len(result.extracted_attachments) == 1
    assert "日报" in result.cleaned_content
