"""检查本地 Python、Ollama 模型和数据目录，不初始化 RAG 模型。"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
REQUIRED_MODELS = ("bge-m3", "gemma3:4b", "gemma4:e4b", "qwen3:0.6b")
_REQUEST_TIMEOUT_SECONDS = 5.0


def _fetch_json(url: str, timeout: float) -> Any:
    scheme = urlsplit(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("environment checks only support http or https URLs")
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        response = client.get(url, headers={"User-Agent": "RAGForgeEnvironmentCheck/0.1"})
        response.raise_for_status()
        return response.json()


def _error(code: str, exc: Exception) -> dict[str, str]:
    return {"code": code, "message": str(exc)[:200] or code}


def _check_package() -> dict[str, Any]:
    try:
        importlib.import_module("ragforge")
    except Exception as exc:  # noqa: BLE001 - diagnostics must return a report instead of crashing.
        return {"ok": False, "error": _error("import_error", exc)}
    return {"ok": True, "error": None}


def _check_ollama(
    ollama_url: str,
    required_models: tuple[str, ...],
    fetch_json,
) -> tuple[dict[str, Any], list[str]]:
    try:
        payload = fetch_json(f"{ollama_url.rstrip('/')}/api/tags", _REQUEST_TIMEOUT_SECONDS)
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise TypeError("response must contain a models list")
        available_names = [
            item["name"]
            for item in payload["models"]
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
    except (TimeoutError, httpx.TimeoutException) as exc:
        return {"ok": False, "url": ollama_url, "models": [], "error": _error("timeout", exc)}, list(required_models)
    except (ConnectionError, httpx.RequestError, httpx.HTTPStatusError, OSError) as exc:
        return {
            "ok": False,
            "url": ollama_url,
            "models": [],
            "error": _error("connection_error", exc),
        }, list(required_models)
    except (TypeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "url": ollama_url,
            "models": [],
            "error": _error("invalid_response", exc),
        }, list(required_models)
    except Exception as exc:  # noqa: BLE001 - classify unexpected client failures in the report.
        return {
            "ok": False,
            "url": ollama_url,
            "models": [],
            "error": _error("unexpected_error", exc),
        }, list(required_models)

    available_names = set(available_names)

    def _is_available(required: str) -> bool:
        if required == "bge-m3":
            return required in available_names or "bge-m3:latest" in available_names
        return required in available_names

    missing = [model for model in required_models if not _is_available(model)]
    return {
        "ok": True,
        "url": ollama_url,
        "models": sorted(available_names),
        "error": None,
    }, missing


def _check_data_dir(data_dir: Path) -> dict[str, Any]:
    resolved = data_dir.expanduser().resolve()
    probe = resolved / f".ragforge-write-test-{uuid4().hex}"
    try:
        resolved.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # noqa: BLE001 - report filesystem failures without crashing.
        try:
            if probe.exists():
                probe.unlink()
        except OSError:
            pass
        return {"ok": False, "path": str(resolved), "error": _error("not_writable", exc)}
    return {"ok": True, "path": str(resolved), "error": None}


def _runtime_profile() -> dict[str, Any]:
    """Inspect the configured runtime without loading embedding/generation models."""
    from ragforge.config import Settings
    from ragforge.index_manifest import build_index_manifest, ensure_compatible, load_manifest

    settings = Settings()
    manifest_path = settings.index_manifest_path.expanduser().resolve()
    manifest = None
    manifest_status = "absent"
    manifest_error = None
    try:
        manifest = load_manifest(manifest_path)
        if manifest is not None:
            expected = build_index_manifest(
                settings,
                dimension=settings.embedder_dim,
                backend={
                    "qdrant": "qdrant_server",
                    "qdrant_local": "qdrant_local",
                    "qdrant_server": "qdrant_server",
                }.get(settings.vector_store, "in_memory"),
                active_collection=manifest.get("active_collection", settings.qdrant_collection),
            )
            ensure_compatible(manifest, expected)
            manifest_status = "compatible"
    except Exception as exc:  # diagnostics must classify, never leak config values
        manifest_status = "invalid_or_mismatch"
        manifest_error = type(exc).__name__

    indexed_chunks = 0
    index_status = "not_persistent"
    if settings.vector_store in {"qdrant", "qdrant_local", "qdrant_server"}:
        index_status = "unavailable"
        client = None
        try:
            from qdrant_client import QdrantClient

            if settings.vector_store in {"qdrant", "qdrant_server"}:
                client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key or None,
                    timeout=2,
                )
            else:
                client = QdrantClient(path=str(settings.qdrant_path))
            collection = (manifest or {}).get("active_collection", settings.qdrant_collection)
            if client.collection_exists(collection):
                indexed_chunks = int(client.count(collection_name=collection, exact=True).count)
            index_status = "ready" if indexed_chunks else "empty"
        except Exception as exc:  # no credentials or endpoint details in report
            manifest_error = manifest_error or type(exc).__name__
        finally:
            if client is not None:
                client.close()

    if settings.vector_store == "in_memory":
        knowledge_state = "empty"
    elif index_status == "ready" and manifest_status == "compatible":
        knowledge_state = "ready"
    elif index_status == "empty":
        knowledge_state = "empty"
    else:
        knowledge_state = "unavailable"

    return {
        "vector_store": settings.vector_store,
        "embedder_backend": settings.embedder_backend,
        "embedder_model": settings.embedder_model,
        "generation_backend": settings.generation_backend,
        "qdrant_collection": settings.qdrant_collection,
        "active_collection": (manifest or {}).get("active_collection"),
        "index_manifest_path": str(manifest_path),
        "manifest_status": manifest_status,
        "manifest_schema_version": (manifest or {}).get("schema_version"),
        "manifest_error": manifest_error,
        "indexed_chunks": indexed_chunks,
        "index_status": index_status,
        "knowledge_state": knowledge_state,
    }


def check_environment(
    ollama_url: str = DEFAULT_OLLAMA_URL,
    data_dir: Path | str = Path("data"),
    required_models: tuple[str, ...] = REQUIRED_MODELS,
    fetch_json=None,
) -> dict[str, Any]:
    """返回稳定的环境检查报告；fetch_json 可注入以便离线测试。"""
    fetch = _fetch_json if fetch_json is None else fetch_json
    package = _check_package()
    ollama, missing_models = _check_ollama(ollama_url, tuple(required_models), fetch)
    data = _check_data_dir(Path(data_dir))
    runtime = _runtime_profile()
    return {
        "schema_version": 1,
        "python": {
            "ok": True,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "executable": sys.executable,
        },
        "package": package,
        "ollama": ollama,
        "required_models": list(required_models),
        "missing_models": missing_models,
        "data": data,
        "runtime": runtime,
        "ok": bool(package["ok"] and ollama["ok"] and data["ok"] and not missing_models),
    }


def _print_text(report: dict[str, Any]) -> None:
    print(f"Python: {'OK' if report['python']['ok'] else 'FAIL'} ({report['python']['version']})")
    print(f"Package: {'OK' if report['package']['ok'] else 'FAIL'}")
    print(f"Ollama: {'OK' if report['ollama']['ok'] else 'FAIL'} ({report['ollama']['url']})")
    print("Models:")
    available_models = set(report["ollama"]["models"])
    for model in report["required_models"]:
        present = model in available_models or (model == "bge-m3" and "bge-m3:latest" in available_models)
        print(f"  {model}: {'OK' if present else 'MISSING'}")
    print(f"Data: {'OK' if report['data']['ok'] else 'FAIL'} ({report['data']['path']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)

    report = check_environment(args.ollama_url, args.data_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
