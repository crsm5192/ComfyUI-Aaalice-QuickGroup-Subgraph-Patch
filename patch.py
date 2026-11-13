"""Install or remove the QuickGroupManager subgraph patch. No dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

VERSION = "1.0.0"
BACKUP = ".aaalice-quickgroup-subgraph-patch"
HELPER = "js/lib/quick_group_manager_subgraphs.js"
RUNTIME = "js/lib/quick_group_manager_runtime.js"
NAVIGATION = "js/lib/group_navigation.js"
PAYLOAD = Path(__file__).resolve().parent / "payload"


class PatchError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise PatchError(f"Unsupported source at {label}; no files were changed.")
    return source.replace(old, new, 1)


def replace_section(source: str, start: str, end: str, replacement: str) -> str:
    if source.count(start) != 1 or source.count(end) != 1:
        raise PatchError("Unsupported QuickGroupManager source; no files were changed.")
    left = source.index(start)
    right = source.index(end, left)
    return source[:left] + replacement + "\n\n" + source[right:]


def patched_sources(target: Path) -> dict[str, bytes]:
    runtime_bytes = (target / RUNTIME).read_bytes()
    navigation_bytes = (target / NAVIGATION).read_bytes()
    runtime = runtime_bytes.decode("utf-8").replace("\r\n", "\n")
    navigation = navigation_bytes.decode("utf-8").replace("\r\n", "\n")
    runtime = replace_once(runtime, 'const NODE_TYPE = "QuickGroupManager";',
        'import { allGraphNodes, rootGraph } from "./graph_scope.js";\n'
        'import { managedGroupEntries, managedGroupView } from "./quick_group_manager_subgraphs.js";\n\n'
        'const NODE_TYPE = "QuickGroupManager";', "runtime imports")
    runtime = replace_section(runtime, "function sameNodes(", "export function quickGroupManagerSnapshot(", '''export function quickGroupManagerGroups(node) {
	return managedGroupEntries(node?.graph).map((entry) => {
		const { group, graph } = entry;
		let refreshFailed = false;
		try {
			group.recomputeInsideNodes?.();
		} catch (error) {
			refreshFailed = true;
			console.error("[Aaalice] Could not refresh QuickGroupManager group members", group, error);
		}
		let nodes = collectGroupNodes(group);
		if (!nodes.length) nodes = geometricGroupNodes(group, graph);
		if (!nodes.length && refreshFailed && Array.isArray(group.nodes)) nodes = group.nodes;
		return managedGroupView(group, nodes, entry);
	});
}''')
    runtime = replace_once(runtime, "function commitGraph(node, mutate, { transaction = true } = {}) {\n\tconst graph = node?.graph;",
        "function commitGraph(node, mutate, { transaction = true } = {}) {\n\tconst graph = rootGraph(node?.graph);", "workflow transaction")
    runtime = replace_section(runtime, "export function refreshQuickGroupManagerControls(", "function nodeIdentity(", '''export function refreshQuickGroupManagerControls(node) {
	const managers = new Set([node, ...allGraphNodes(node?.graph).filter(isQuickGroupManager)]);
	for (const manager of managers) {
		for (const refresh of manager?._aaaliceQuickGroupControlRefreshes || []) refresh();
	}
}''')
    navigation = replace_once(navigation, "function finitePair(value) {",
        'import { openManagedGroupGraph } from "./quick_group_manager_subgraphs.js";\n\nfunction finitePair(value) {', "navigation import")
    navigation = replace_once(navigation, "\tif (!canvas || !group) return false;\n\tconst bounds = groupNavigationBounds(group);",
        "\tif (!canvas || !group) return false;\n\tif (!openManagedGroupGraph(canvas, group)) return false;\n\tgroup = group._aaaliceOriginalGroup || group;\n\tconst bounds = groupNavigationBounds(group);", "group navigation")
    result = {}
    for name, text, original in [(RUNTIME, runtime, runtime_bytes), (NAVIGATION, navigation, navigation_bytes)]:
        if b"\r\n" in original:
            text = text.replace("\n", "\r\n")
        result[name] = text.encode("utf-8")
    result[HELPER] = (PAYLOAD / Path(HELPER).name).read_bytes()
    return result


def target_path(value: str) -> Path:
    target = Path(value).expanduser().resolve()
    if not all((target / path).is_file() for path in [RUNTIME, NAVIGATION, "js/lib/graph_scope.js"]):
        raise PatchError("Target must be the ComfyUI-Aaalice-Nodes directory.")
    return target


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".subgraph-patch.tmp")
    created = False
    try:
        with temporary.open("xb") as stream:
            created = True
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def manifest_for(target: Path) -> dict | None:
    backup = target / BACKUP
    if not backup.exists():
        return None
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        raise PatchError(f"Incomplete backup at {backup}; inspect it before retrying.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != VERSION or set(manifest.get("files", {})) != {RUNTIME, NAVIGATION, HELPER}:
        raise PatchError("Unrecognized patch backup.")
    return manifest


def verify_installed(target: Path, manifest: dict) -> None:
    for name, saved in manifest["files"].items():
        path = target / name
        if not path.is_file() or digest(path.read_bytes()) != saved["patched"]:
            raise PatchError(f"{name} changed after installation. Keep your edits; restore manually from {BACKUP}.")


def install(target: Path) -> str:
    manifest = manifest_for(target)
    if manifest:
        verify_installed(target, manifest)
        return "Already installed."
    if (target / HELPER).exists():
        raise PatchError(f"{HELPER} already exists; no files were changed.")
    replacements = patched_sources(target)
    originals = {name: (target / name).read_bytes() if (target / name).exists() else None for name in replacements}
    backup = target / BACKUP
    backup.mkdir()
    manifest = {"version": VERSION, "files": {}}
    for name, data in replacements.items():
        original = originals[name]
        if original is not None:
            copy = backup / name
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(original)
        manifest["files"][name] = {"original": digest(original) if original is not None else None, "patched": digest(data)}
    changed = []
    try:
        for name, data in replacements.items():
            atomic_write(target / name, data)
            changed.append(name)
        (backup / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except OSError:
        for name in reversed(changed):
            if originals[name] is None:
                (target / name).unlink(missing_ok=True)
            else:
                atomic_write(target / name, originals[name])
        raise PatchError(f"Installation failed; changed files were rolled back. Inspect {backup} before retrying.") from None
    return "Installed. Restart ComfyUI and hard-refresh the browser (Ctrl+F5)."


def uninstall(target: Path) -> str:
    manifest = manifest_for(target)
    if manifest is None:
        return "Not installed."
    verify_installed(target, manifest)
    backup = target / BACKUP
    originals = {}
    for name, saved in manifest["files"].items():
        if saved["original"] is None:
            originals[name] = None
            continue
        copy = backup / name
        if not copy.is_file() or digest(copy.read_bytes()) != saved["original"]:
            raise PatchError(f"Backup verification failed for {name}; no files were changed.")
        originals[name] = copy.read_bytes()
    patched = {name: (target / name).read_bytes() for name in originals}
    changed = []
    try:
        for name, data in originals.items():
            if data is None:
                (target / name).unlink()
            else:
                atomic_write(target / name, data)
            changed.append(name)
    except OSError:
        for name in reversed(changed):
            atomic_write(target / name, patched[name])
        raise PatchError("Uninstall failed; patched files were restored.") from None
    for name, data in originals.items():
        if data is not None:
            (backup / name).unlink()
    (backup / "js/lib").rmdir()
    (backup / "js").rmdir()
    (backup / "manifest.json").unlink()
    backup.rmdir()
    return "Uninstalled. Restart ComfyUI and hard-refresh the browser (Ctrl+F5)."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "install", "uninstall"])
    parser.add_argument("--target", required=True, help="Path to ComfyUI-Aaalice-Nodes")
    args = parser.parse_args()
    try:
        target = target_path(args.target)
        if args.action == "install":
            message = install(target)
        elif args.action == "uninstall":
            message = uninstall(target)
        else:
            manifest = manifest_for(target)
            if manifest:
                verify_installed(target, manifest)
                message = "Installed and verified."
            else:
                patched_sources(target)
                message = "Compatible; patch is not installed."
        print(message)
        return 0
    except (PatchError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
