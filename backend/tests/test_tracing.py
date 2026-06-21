"""
Langfuse 追踪器测试（未配置时走空实现）
"""

from core.config import Settings
from core.tracing import LangfuseTracer, NoOpTrace


def test_tracer_disabled_without_credentials():
    settings = Settings(
        langfuse_public_key=None,
        langfuse_secret_key=None,
    )
    tracer = LangfuseTracer(settings)
    assert tracer.is_enabled() is False


def test_noop_trace_context():
    with NoOpTrace() as trace:
        assert trace.metadata == {}
        trace.update(output="test")


def test_trace_yields_noop_when_disabled():
    settings = Settings(
        langfuse_public_key=None,
        langfuse_secret_key=None,
    )
    tracer = LangfuseTracer(settings)
    with tracer.trace(name="test") as trace:
        assert isinstance(trace, NoOpTrace)
        with tracer.span(trace, "inner") as span:
            assert isinstance(span, NoOpTrace)
