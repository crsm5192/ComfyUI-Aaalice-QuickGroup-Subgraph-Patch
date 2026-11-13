// verify_target.py runs this against a patched temporary copy of the real package.
import test from "node:test";
import assert from "node:assert/strict";
import { applyQuickGroupManagerAction, applyQuickGroupManagerPreset, quickGroupManagerPresetSnapshot, quickGroupManagerSnapshot, setQuickGroupManagerOffMode } from "../js/lib/quick_group_manager_runtime.js";
import { navigateToVisualGroup } from "../js/lib/group_navigation.js";

function graph(id) {
	return { id, _groups: [], _nodes: [], changes: 0, before: 0, after: 0,
		beforeChange() { this.before++; }, afterChange() { this.after++; }, change() { this.changes++; }, setDirtyCanvas() {} };
}
function addGroup(owner, id = 1, mode = 0, color = "#88a") {
	const member = { id: 5, mode, graph: owner, pos: [20, 20], size: [40, 40] };
	const group = { id, title: "Group", color, graph: owner, nodes: [member], boundingRect: [0, 0, 100, 100], recomputeInsideNodes() {} };
	owner._groups.push(group);
	owner._nodes.push(member);
	return group;
}
function manager(owner, state = {}) {
	const result = { id: 100, graph: owner, type: "QuickGroupManager", properties: { quickGroupManagerState: state } };
	owner._nodes.push(result);
	return result;
}
function fixture() {
	const root = graph("root"), a = graph("a"), b = graph("b"), deep = graph("deep");
	for (const [parent, child, id] of [[root, a, 10], [root, b, 20], [a, deep, 30]]) {
		child.rootGraph = root;
		parent._nodes.push({ id, title: child.id, mode: 0, graph: parent, subgraph: child });
	}
	const groups = [root, a, b, deep].map((owner) => addGroup(owner));
	return { root, a, b, deep, groups, current: manager(root) };
}

test("same numeric ids in four graphs remain independently switchable", () => {
	const { current, groups } = fixture();
	const snapshot = quickGroupManagerSnapshot(current);
	assert.deepEqual(snapshot.groups.map((group) => group.id), [1, "subgraph/a/1", "subgraph/deep/1", "subgraph/b/1"]);
	assert.equal(snapshot.groups[2].title, "a / deep / Group");
	assert.equal(applyQuickGroupManagerAction(current, "subgraph/deep/1", "disable").ok, true);
	assert.deepEqual(groups.map((group) => group.nodes[0].mode), [0, 0, 0, 2]);
	assert.deepEqual(groups.map((group) => group.id), [1, 1, 1, 1]);
});

test("links root to subgraph nodes in one root workflow transaction", () => {
	const { current, root, groups } = fixture();
	current.properties.quickGroupManagerState.rules = { 1: { disable: { "subgraph/a/1": "disable", "subgraph/b/1": "disable" } } };
	assert.equal(applyQuickGroupManagerAction(current, 1, "disable").ok, true);
	assert.deepEqual(groups.map((group) => group.nodes[0].mode), [2, 2, 2, 0]);
	assert.deepEqual([root.before, root.after, root.changes], [1, 1, 1]);
});

test("nested managers see descendants and refresh all controls through the root", () => {
	const { current, root, a, groups } = fixture();
	const inner = manager(a);
	let outerRefresh = 0, innerRefresh = 0;
	current._aaaliceQuickGroupControlRefreshes = new Set([() => outerRefresh++]);
	inner._aaaliceQuickGroupControlRefreshes = new Set([() => innerRefresh++]);
	assert.deepEqual(quickGroupManagerSnapshot(inner).groups.map((group) => group.id), [1, "subgraph/deep/1"]);
	assert.equal(applyQuickGroupManagerAction(inner, 1, "disable").ok, true);
	assert.equal(groups[1].nodes[0].mode, 2);
	assert.deepEqual([outerRefresh, innerRefresh, root.before, a.before], [1, 1, 1, 0]);
});

test("filter, ordering and off mode work across subgraph scope", () => {
	const { current, groups } = fixture();
	groups[2].color = "#ff0000";
	groups[3].nodes[0].mode = 2;
	current.properties.quickGroupManagerState = { groupOrder: ["subgraph/deep/1", "1"], filter: { mode: "selected", colors: ["#88a"] } };
	assert.deepEqual(quickGroupManagerSnapshot(current).visibleGroups.map((group) => String(group.id)), ["subgraph/deep/1", "1", "subgraph/a/1"]);
	assert.equal(setQuickGroupManagerOffMode(current, "bypass").ok, true);
	assert.equal(groups[3].nodes[0].mode, 4);
	assert.equal(groups[2].nodes[0].mode, 0);
});

test("presets with repeated node and group ids restore their own live definitions", () => {
	const { current, groups } = fixture();
	groups[1].nodes[0].mode = 2;
	groups[3].nodes[0].mode = 4;
	const saved = quickGroupManagerPresetSnapshot(current);
	for (const group of groups) group.nodes[0].mode = 0;
	assert.equal(applyQuickGroupManagerPreset(current, saved).ok, true);
	assert.deepEqual(groups.map((group) => group.nodes[0].mode), [0, 2, 0, 2]);
});

test("recovers an empty subgraph cache from that graph's geometry", () => {
	const { current, groups } = fixture();
	const originalMember = groups[1].nodes[0];
	groups[1].nodes = [];
	groups[1]._bounding = [0, 0, 100, 100];
	assert.equal(applyQuickGroupManagerAction(current, "subgraph/a/1", "disable").ok, true);
	assert.equal(originalMember.mode, 2);
	assert.equal(groups[0].nodes[0].mode, 0);
});

test("group locator switches graph and fits the original native bounds", () => {
	const { current, root, deep } = fixture();
	const group = quickGroupManagerSnapshot(current).groups.find((group) => group.id === "subgraph/deep/1");
	const calls = [];
	const canvas = { graph: root, openSubgraph(next, from) { calls.push(["open", next.id, from.id]); this.graph = next; }, ds: { fitToBounds(bounds) { calls.push(["fit", bounds]); } }, setDirty() {} };
	assert.equal(navigateToVisualGroup(canvas, group), true);
	assert.equal(canvas.graph, deep);
	assert.deepEqual(calls, [["open", "deep", 30], ["fit", [0, 0, 100, 100]]]);
});
