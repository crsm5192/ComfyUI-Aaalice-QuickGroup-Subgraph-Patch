import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch as mock_patch

PROJECT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("patch", PROJECT / "patch.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

RUNTIME = '''const NODE_TYPE = "QuickGroupManager";
function sameNodes(left, right) { return false; }
export function quickGroupManagerSnapshot(node) { return node; }
function commitGraph(node, mutate, { transaction = true } = {}) {
\tconst graph = node?.graph;
}
export function refreshQuickGroupManagerControls(node) {}
function nodeIdentity(node) { return node.id; }
'''
NAVIGATION = '''function finitePair(value) { return true; }
export function navigateToVisualGroup(canvas, group) {
\tif (!canvas || !group) return false;
\tconst bounds = groupNavigationBounds(group);
}
'''


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.target = Path(self.temporary.name)
        (self.target / "js/lib").mkdir(parents=True)
        (self.target / patch.RUNTIME).write_bytes(RUNTIME.replace("\n", "\r\n").encode())
        (self.target / patch.NAVIGATION).write_bytes(NAVIGATION.encode())
        (self.target / "js/lib/graph_scope.js").write_text("", encoding="utf-8")
        self.originals = {name: (self.target / name).read_bytes() for name in [patch.RUNTIME, patch.NAVIGATION]}

    def test_install_is_idempotent_and_uninstall_restores_exact_bytes(self):
        self.assertIn("Installed", patch.install(self.target))
        self.assertEqual(patch.install(self.target), "Already installed.")
        patch.verify_installed(self.target, patch.manifest_for(self.target))
        runtime = (self.target / patch.RUNTIME).read_bytes()
        self.assertIn(b"managedGroupEntries", runtime)
        self.assertNotIn(b"\n", runtime.replace(b"\r\n", b""))
        self.assertIn("Uninstalled", patch.uninstall(self.target))
        for name, data in self.originals.items():
            self.assertEqual((self.target / name).read_bytes(), data)
        self.assertFalse((self.target / patch.HELPER).exists())
        self.assertFalse((self.target / patch.BACKUP).exists())
        self.assertEqual(patch.uninstall(self.target), "Not installed.")

    def test_unsupported_version_does_not_change_any_file(self):
        (self.target / patch.RUNTIME).write_text("unsupported", encoding="utf-8")
        with self.assertRaises(patch.PatchError):
            patch.install(self.target)
        self.assertEqual((self.target / patch.RUNTIME).read_text(), "unsupported")
        self.assertEqual((self.target / patch.NAVIGATION).read_bytes(), self.originals[patch.NAVIGATION])
        self.assertFalse((self.target / patch.BACKUP).exists())

    def test_post_install_edits_are_preserved(self):
        patch.install(self.target)
        edited = (self.target / patch.RUNTIME).read_bytes() + b"// user edit\n"
        (self.target / patch.RUNTIME).write_bytes(edited)
        with self.assertRaises(patch.PatchError):
            patch.uninstall(self.target)
        self.assertEqual((self.target / patch.RUNTIME).read_bytes(), edited)
        self.assertTrue((self.target / patch.HELPER).exists())

    def test_corrupted_backup_is_rejected_before_uninstall(self):
        patch.install(self.target)
        (self.target / patch.BACKUP / patch.RUNTIME).write_text("broken", encoding="utf-8")
        with self.assertRaises(patch.PatchError):
            patch.uninstall(self.target)
        patch.verify_installed(self.target, patch.manifest_for(self.target))

    def test_existing_helper_is_preserved(self):
        (self.target / patch.HELPER).write_text("existing", encoding="utf-8")
        with self.assertRaises(patch.PatchError):
            patch.install(self.target)
        self.assertEqual((self.target / patch.HELPER).read_text(), "existing")
        self.assertFalse((self.target / patch.BACKUP).exists())

    def test_failed_install_rolls_back_completed_writes(self):
        write = patch.atomic_write
        calls = 0

        def fail_second(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated write failure")
            return write(path, data)

        with mock_patch.object(patch, "atomic_write", fail_second):
            with self.assertRaises(patch.PatchError):
                patch.install(self.target)
        for name, data in self.originals.items():
            self.assertEqual((self.target / name).read_bytes(), data)
        self.assertFalse((self.target / patch.HELPER).exists())

    def test_failed_uninstall_restores_patched_files(self):
        patch.install(self.target)
        write = patch.atomic_write
        calls = 0

        def fail_second(path, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated write failure")
            return write(path, data)

        with mock_patch.object(patch, "atomic_write", fail_second):
            with self.assertRaises(patch.PatchError):
                patch.uninstall(self.target)
        patch.verify_installed(self.target, patch.manifest_for(self.target))

    def test_existing_temporary_file_is_preserved(self):
        destination = self.target / patch.RUNTIME
        temporary = destination.with_name(destination.name + ".subgraph-patch.tmp")
        temporary.write_bytes(b"existing temporary file")
        with self.assertRaises(FileExistsError):
            patch.atomic_write(destination, b"new data")
        self.assertEqual(temporary.read_bytes(), b"existing temporary file")
        self.assertEqual(destination.read_bytes(), self.originals[patch.RUNTIME])


if __name__ == "__main__":
    unittest.main()
