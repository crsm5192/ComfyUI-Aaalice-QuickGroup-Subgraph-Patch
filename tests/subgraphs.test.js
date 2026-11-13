import test from "node:test";
import assert from "node:assert/strict";
import { managedGroupEntries, managedGroupView, openManagedGroupGraph } from "../payload/quick_group_manager_subgraphs.js";

function graph(id, groups = []) { return { id, _groups: groups, _nodes: [] }; }
function wrapper(parent, child, id, title) {
	const node = { id, title, graph: parent, subgraph: child };
	parent._nodes.push(node);
	child.rootGraph = parent.rootGraph || parent;
	return node;
}

test("discovers local, child and deeply nested groups without scanning siblings", () => {
	const root = graph("root", [{ id: 1 }]);
	const child = graph("child", [{ id: 1 }]);
	const deep = graph("deep", [{ id: 1 }]);
	const sibling = graph("sibling", [{ id: 1 }]);
	const a = wrapper(root, child, 10, "A");
	const b = wrapper(child, deep, 20, "B");
	wrapper(root, sibling, 30, "C");
	const entries = managedGroupEntries(child);
	assert.deepEqual(entries.map((entry) => entry.graph.id), ["child", "deep"]);
	assert.deepEqual(entries[1].path, [b]);
	assert.deepEqual(managedGroupEntries(root)[2].path, [a, b]);
});

test("handles shared definitions, cycles, null groups and iterable collections", () => {
	const root = graph("root");
	const child = graph("child", [null, { id: 1 }]);
	wrapper(root, child, 10, "A");
	wrapper(root, child, 20, "B");
	child._nodes.push({ id: 30, subgraph: root });
	root.nodes = new Set(root._nodes);
	child.groups = new Set(child._groups);
	assert.equal(managedGroupEntries(root).length, 1);
	assert.deepEqual(managedGroupEntries(null), []);
});

test("qualifies descendant ids and titles while retaining live node references and native getters", () => {
	const root = graph("root");
	const child = graph("child/uuid");
	const path = [wrapper(root, child, 10, "Stage")];
	const member = { id: 1, mode: 0 };
	class Group {
		id = 1;
		title = "Render";
		_nodes = [member];
		get nodes() { return this._nodes; }
		get color() { return "#88a"; }
		get boundingRect() { return [10, 20, 30, 40]; }
	}
	const original = new Group();
	const view = managedGroupView(original, [member], { graph: child, path });
	assert.equal(view.id, "subgraph/child%2Fuuid/1");
	assert.equal(view.title, "Stage / Render");
	assert.equal(view.color, "#88a");
	assert.deepEqual(view.boundingRect, [10, 20, 30, 40]);
	assert.equal(view.nodes[0], member);
	assert.equal(view._aaaliceOriginalGroup, original);
	assert.equal(original.id, 1);
	assert.equal(original.title, "Render");
	assert.equal(managedGroupView(original, [member], { graph: root, path: [] }), original);
	path[0].title = "Renamed";
	assert.equal(managedGroupView(original, [member], { graph: child, path }).id, view.id);
});

test("uses stable wrapper paths for graphs without ids", () => {
	const root = graph("root");
	const child = graph(undefined);
	const path = [wrapper(root, child, 10, "A")];
	assert.equal(managedGroupView({ id: 1, title: "G" }, [], { graph: child, path }).id, "subgraph/10/1");
});

test("navigates to the native subgraph before fitting a group and returns to root", () => {
	const root = graph("root");
	const child = graph("child");
	const deep = graph("deep");
	const a = wrapper(root, child, 10, "A");
	const b = wrapper(child, deep, 20, "B");
	const calls = [];
	const canvas = { graph: root, openSubgraph(next, from) { calls.push([next, from]); this.graph = next; }, setGraph(next) { this.graph = next; } };
	assert.equal(openManagedGroupGraph(canvas, { graph: deep, _aaaliceGraphPath: [a, b] }), true);
	assert.deepEqual(calls, [[deep, b]]);
	assert.equal(openManagedGroupGraph(canvas, { graph: root }), true);
	assert.equal(canvas.graph, root);
	assert.equal(openManagedGroupGraph(canvas, { graph: graph("other") }), false);
	assert.equal(canvas.graph, root);
});

test("reports unavailable or cancelled navigation and preserves graphless targets", () => {
	const root = graph("root");
	const child = graph("child");
	const path = [wrapper(root, child, 1, "A")];
	assert.equal(openManagedGroupGraph({ graph: root }, { graph: child, _aaaliceGraphPath: path }), false);
	assert.equal(openManagedGroupGraph({ graph: root, openSubgraph() {} }, { graph: child, _aaaliceGraphPath: path }), false);
	assert.equal(openManagedGroupGraph({}, {}), true);
});
