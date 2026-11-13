"""Exercise the installed entry point and real aiohttp static module requests."""

import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch as mock_patch
from uuid import uuid4

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from test_installer import RUNTIME, NAVIGATION

PROJECT = Path(__file__).resolve().parents[1]
TARGET = "ComfyUI-Aaalice-Nodes"
STATUS = "/aaalice-quickgroup-subgraph-patch/status"


class ExtensionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.target = Path(self.temporary.name) / TARGET
        (self.target / "js/lib").mkdir(parents=True)
        self.originals = {
            "js/lib/quick_group_manager_runtime.js": RUNTIME.encode(),
            "js/lib/group_navigation.js": NAVIGATION.encode(),
            "js/lib/graph_scope.js": b"// original scope module\n",
        }
        for filename, data in self.originals.items():
            (self.target / filename).write_bytes(data)

        @web.middleware
        async def security(request, handler):
            if request.headers.get("X-Test-Deny"):
                return web.Response(status=403, text="denied by outer middleware")
            return await handler(request)

        self.application = web.Application(middlewares=[security])
        # The original package can be loaded AFTER this extension.
        self.registry = SimpleNamespace(EXTENSION_WEB_DIRS={})
        self.package_name = "aaalice_extension_test_" + uuid4().hex
        spec = importlib.util.spec_from_file_location(self.package_name, PROJECT / "__init__.py")
        self.entry = importlib.util.module_from_spec(spec)
        sys.modules[self.package_name] = self.entry
        self.addCleanup(self.remove_modules)
        with mock_patch.dict(sys.modules, {
            "nodes": self.registry,
            "server": SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(app=self.application))),
        }):
            spec.loader.exec_module(self.entry)
            self.extension = sys.modules[self.package_name + ".extension"]
            self.patch = sys.modules[self.package_name + ".patch"]
        self.registry.EXTENSION_WEB_DIRS[TARGET] = str(self.target / "js")
        self.application.router.add_static("/extensions/" + TARGET, self.target / "js")
        self.client = TestClient(TestServer(self.application))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    def remove_modules(self):
        for name in list(sys.modules):
            if name == self.package_name or name.startswith(self.package_name + "."):
                del sys.modules[name]

    async def status(self):
        response = await self.client.get(STATUS)
        self.assertEqual(response.status, 200)
        return await response.json()

    def assert_original_files(self):
        for filename, original in self.originals.items():
            self.assertEqual((self.target / filename).read_bytes(), original)
        self.assertFalse((self.target / self.patch.HELPER).exists())
        self.assertFalse((self.target / self.patch.BACKUP).exists())

    async def test_entry_is_a_valid_frontend_only_comfyui_extension(self):
        self.assertEqual(self.entry.NODE_CLASS_MAPPINGS, {})
        self.assertEqual(self.entry.NODE_DISPLAY_NAME_MAPPINGS, {})
        self.assertTrue((PROJECT / self.entry.WEB_DIRECTORY / "extension.js").is_file())
        self.assertTrue((await self.status())["active"])
        self.assert_original_files()

    async def test_runtime_navigation_and_helper_are_served_at_original_import_urls(self):
        expected = self.patch.patched_sources(self.target)
        for filename, data in expected.items():
            url = "/extensions/" + TARGET + "/" + filename.removeprefix("js/")
            response = await self.client.get(url + "?v=cache-buster")
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.read(), data)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.content_type, "application/javascript")
        self.assert_original_files()

    async def test_original_module_and_unknown_routes_are_unchanged(self):
        response = await self.client.get("/extensions/" + TARGET + "/lib/graph_scope.js")
        self.assertEqual(await response.read(), self.originals["js/lib/graph_scope.js"])
        response = await self.client.get("/extensions/OtherPackage/lib/quick_group_manager_runtime.js")
        self.assertEqual(response.status, 404)
        response = await self.client.get("/unrelated")
        self.assertEqual(response.status, 404)

    async def test_security_middleware_is_preserved(self):
        response = await self.client.get(STATUS, headers={"X-Test-Deny": "1"})
        self.assertEqual(response.status, 403)
        response = await self.client.get("/extensions/" + TARGET + "/lib/quick_group_manager_runtime.js",
                                         headers={"X-Test-Deny": "1"})
        self.assertEqual(response.status, 403)

    async def test_head_api_prefix_and_post_requests(self):
        response = await self.client.head("/extensions/" + TARGET + "/lib/quick_group_manager_subgraphs.js")
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.read(), b"")
        response = await self.client.get("/api" + STATUS)
        self.assertEqual((await response.json())["state"], "active")
        response = await self.client.post("/extensions/" + TARGET + "/lib/quick_group_manager_runtime.js")
        self.assertEqual(response.status, 405)

    async def test_missing_or_disabled_original_package_is_reported(self):
        self.registry.EXTENSION_WEB_DIRS.clear()
        status = await self.status()
        self.assertFalse(status["active"])
        self.assertEqual(status["state"], "missing")
        response = await self.client.get("/extensions/" + TARGET + "/lib/quick_group_manager_subgraphs.js")
        self.assertEqual(response.status, 404)
        self.assert_original_files()

    async def test_unsupported_source_leaves_original_extension_working(self):
        filename = "js/lib/quick_group_manager_runtime.js"
        (self.target / filename).write_bytes(b"// updated upstream implementation\n")
        status = await self.status()
        self.assertEqual(status["state"], "incompatible")
        self.assertFalse(status["active"])
        self.assertTrue(status["errors"])
        response = await self.client.get("/extensions/" + TARGET + "/lib/quick_group_manager_runtime.js")
        self.assertEqual(await response.read(), b"// updated upstream implementation\n")
        self.assertFalse((self.target / self.patch.BACKUP).exists())

    async def test_registry_aliases_share_the_same_patched_sources(self):
        alias = "comfyui-aaalice-nodes"
        self.registry.EXTENSION_WEB_DIRS[alias] = str(self.target / "js")
        response = await self.client.get("/extensions/" + alias + "/lib/quick_group_manager_subgraphs.js")
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.read(), (PROJECT / "payload/quick_group_manager_subgraphs.js").read_bytes())
        self.assert_original_files()

    async def test_valid_legacy_manual_install_is_supported_without_writes(self):
        self.patch.install(self.target)
        before = {filename: (self.target / filename).read_bytes()
                  for filename in (self.patch.RUNTIME, self.patch.NAVIGATION, self.patch.HELPER)}
        status = await self.status()
        self.assertEqual(status["state"], "active")
        self.assertTrue(status["legacy_install"])
        for filename, data in before.items():
            self.assertEqual((self.target / filename).read_bytes(), data)

    async def test_modified_legacy_install_is_reported_and_preserved(self):
        self.patch.install(self.target)
        edited = (self.target / self.patch.RUNTIME).read_bytes() + b"// user edit\n"
        (self.target / self.patch.RUNTIME).write_bytes(edited)
        self.assertEqual((await self.status())["state"], "incompatible")
        self.assertEqual((self.target / self.patch.RUNTIME).read_bytes(), edited)

    async def test_duplicate_registration_is_idempotent_even_after_server_freezes(self):
        with mock_patch.dict(sys.modules, {
            "nodes": self.registry,
            "server": SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(app=self.application))),
        }):
            self.extension.register_extension()
        self.assertEqual(len(self.application.middlewares), 2)
        self.assertTrue((await self.status())["active"])

    async def test_disabling_extension_restores_original_served_files(self):
        await self.status()
        original_application = web.Application()
        original_application.router.add_static("/extensions/" + TARGET, self.target / "js")
        async with TestClient(TestServer(original_application)) as client:
            response = await client.get("/extensions/" + TARGET + "/lib/quick_group_manager_runtime.js")
            self.assertEqual(await response.read(), self.originals[self.patch.RUNTIME])
            response = await client.get("/extensions/" + TARGET + "/lib/quick_group_manager_subgraphs.js")
            self.assertEqual(response.status, 404)
        self.assert_original_files()


if __name__ == "__main__":
    unittest.main()
