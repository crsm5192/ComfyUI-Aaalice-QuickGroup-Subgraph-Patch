"""Serve patched modules at the original URLs without editing the node package."""

from __future__ import annotations

import logging
from pathlib import Path

from . import patch

VERSION = "1.1.0"
TARGET = "ComfyUI-Aaalice-Nodes"
STATUS_PATH = "/aaalice-quickgroup-subgraph-patch/status"
MARKER = "_aaalice_quickgroup_subgraph_patch"
LOGGER = logging.getLogger(__name__)


def prepare_assets(web_directories: dict[str, str]) -> tuple[dict[str, bytes], dict]:
    """Resolve only enabled extensions, after ComfyUI finishes loading packages."""
    assets = {}
    prepared = {}
    errors = []
    legacy = False
    for name, directory in web_directories.items():
        target = Path(directory).resolve().parent
        if target.name.casefold() != TARGET.casefold() and name.casefold() != TARGET.casefold():
            continue
        if target not in prepared:
            try:
                patch.target_path(str(target))
                manifest = patch.manifest_for(target)
                if manifest:
                    patch.verify_installed(target, manifest)
                    sources = {filename: (target / filename).read_bytes()
                               for filename in (patch.RUNTIME, patch.NAVIGATION, patch.HELPER)}
                    legacy = True
                else:
                    sources = patch.patched_sources(target)
                prepared[target] = sources
            except (patch.PatchError, OSError, ValueError) as error:
                prepared[target] = None
                errors.append(str(error))
        sources = prepared[target]
        if sources is not None:
            for filename, data in sources.items():
                assets[f"/extensions/{name}/{filename.removeprefix('js/')}"] = data
    status = {
        "version": VERSION,
        "active": bool(assets),
        "state": "incompatible" if errors else "active" if assets else "missing",
        "legacy_install": legacy,
        "errors": errors,
    }
    return assets, status


def register_extension() -> None:
    """Add one middleware inside ComfyUI's existing security middleware chain."""
    from aiohttp import web
    import nodes
    from server import PromptServer

    application = PromptServer.instance.app
    if any(getattr(middleware, MARKER, False) for middleware in application.middlewares):
        return
    prepared = None

    @web.middleware
    async def serve_patch(request, handler):
        nonlocal prepared
        path = request.path
        is_status = path in (STATUS_PATH, "/api" + STATUS_PATH)
        if request.method not in {"GET", "HEAD"} or not (is_status or path.startswith("/extensions/")):
            return await handler(request)
        if prepared is None:
            prepared = prepare_assets(nodes.EXTENSION_WEB_DIRS)
            status = prepared[1]
            if status["state"] == "active":
                LOGGER.info("[Aaalice Subgraph Patch] Active / 子图补丁已启用 (v%s)", VERSION)
            elif status["state"] == "missing":
                LOGGER.warning("[Aaalice Subgraph Patch] ComfyUI-Aaalice-Nodes is not enabled / 原节点包未安装或未启用")
            else:
                LOGGER.error("[Aaalice Subgraph Patch] Incompatible source / 原节点包版本不兼容: %s",
                             "; ".join(status["errors"]))
        assets, status = prepared
        if is_status:
            return web.json_response(status, headers={"Cache-Control": "no-store"})
        if path in assets:
            return web.Response(body=assets[path], content_type="application/javascript",
                                charset="utf-8", headers={"Cache-Control": "no-store"})
        return await handler(request)

    setattr(serve_patch, MARKER, True)
    application.middlewares.append(serve_patch)
    LOGGER.info("[Aaalice Subgraph Patch] Extension loaded / 扩展已加载 (v%s)", VERSION)
