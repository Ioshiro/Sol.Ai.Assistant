from __future__ import annotations

import base64
import os
from pathlib import Path


DEFAULT_LANGFUSE_HOST = "http://localhost:3000"
DEFAULT_LANGFUSE_PUBLIC_KEY = "lf_pk_local_demo"
DEFAULT_LANGFUSE_SECRET_KEY = "lf_sk_local_demo"

_CONFIGURED = False


def _set_default(name: str, value: str) -> str:
    current = os.environ.get(name)
    if current:
        return current

    os.environ[name] = value
    return value


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _ensure_project_env() -> None:
    project_root = Path(__file__).resolve().parent
    _load_env_file(project_root / ".env")
    _load_env_file(project_root.parent / ".env")


def configure_pipecat_langfuse(service_name: str) -> None:
    """Configure OTLP tracing so Pipecat spans flow into Langfuse."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing tracing dependencies. Install requirements-observability.txt before running the Pipecat bots."
        ) from exc

    _ensure_project_env()

    host = _set_default("LANGFUSE_HOST", DEFAULT_LANGFUSE_HOST).rstrip("/")
    public_key = _set_default("LANGFUSE_PUBLIC_KEY", DEFAULT_LANGFUSE_PUBLIC_KEY)
    secret_key = _set_default("LANGFUSE_SECRET_KEY", DEFAULT_LANGFUSE_SECRET_KEY)

    auth = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    otel_endpoint = f"{host}/api/public/otel"

    _set_default("OTEL_EXPORTER_OTLP_ENDPOINT", otel_endpoint)
    _set_default("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", otel_endpoint)
    _set_default("OTEL_EXPORTER_OTLP_HEADERS", f"Authorization=Basic {auth}")
    _set_default("OTEL_EXPORTER_OTLP_TRACES_HEADERS", f"Authorization=Basic {auth}")
    _set_default("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    _set_default("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "http/protobuf")
    _set_default("OTEL_SERVICE_NAME", service_name)

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    _CONFIGURED = True
