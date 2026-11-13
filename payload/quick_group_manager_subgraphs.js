/** Subgraph scope and navigation for Aaalice QuickGroupManager. */

function items(value) {
	return value?.[Symbol.iterator] ? [...value] : [];
}

export function managedGroupEntries(start) {
	const entries = [];
	const visited = new Set();
	function visit(graph, path) {
		if (!graph || visited.has(graph)) return;
		visited.add(graph);
		for (const group of items(graph.groups ?? graph._groups)) {
			if (group) entries.push({ group, graph, path });
		}
		for (const wrapper of items(graph.nodes ?? graph._nodes)) {
			if (wrapper?.subgraph) visit(wrapper.subgraph, [...path, wrapper]);
		}
	}
	visit(start, []);
	return entries;
}

export function managedGroupView(group, nodes, { graph, path }) {
	const sameNodes = Array.isArray(group.nodes) && group.nodes.length === nodes.length
		&& group.nodes.every((node, index) => node === nodes[index]);
	if (!path.length && (sameNodes || (!Array.isArray(group.nodes) && !nodes.length))) return group;
	const scope = graph.id ?? path.map((wrapper) => wrapper.id).join(":");
	const title = String(group.title || "Untitled group");
	return {
		...group,
		id: path.length ? `subgraph/${encodeURIComponent(scope)}/${encodeURIComponent(group.id)}` : group.id,
		title: path.length ? [...path.map((wrapper) => String(wrapper.title || wrapper.subgraph.name || wrapper.id)), title].join(" / ") : group.title,
		color: group.color,
		nodes,
		graph,
		pos: group.pos,
		size: group.size,
		boundingRect: group.boundingRect,
		_aaaliceOriginalGroup: group,
		_aaaliceGraphPath: path,
	};
}

export function openManagedGroupGraph(canvas, group) {
	const graph = group.graph;
	if (!graph || !canvas.graph || canvas.graph === graph) return true;
	if ((canvas.graph.rootGraph || canvas.graph) !== (graph.rootGraph || graph)) return false;
	const wrapper = group._aaaliceGraphPath?.at(-1);
	if (wrapper && typeof canvas.openSubgraph === "function") canvas.openSubgraph(graph, wrapper);
	else if (typeof canvas.setGraph === "function") canvas.setGraph(graph);
	else return false;
	return canvas.graph === graph;
}
