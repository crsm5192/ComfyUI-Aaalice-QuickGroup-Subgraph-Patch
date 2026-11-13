import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
	name: "crsm5192.AaaliceQuickGroupSubgraphPatch",
	async setup() {
		const language = app.ui?.settings?.getSettingValue("Comfy.Locale")
			|| document.documentElement.lang || navigator.language;
		const chinese = String(language).toLowerCase().startsWith("zh");
		try {
			const response = await api.fetchApi("/aaalice-quickgroup-subgraph-patch/status");
			if (!response.ok) throw new Error(`HTTP ${response.status}`);
			const status = await response.json();
			if (status.state === "active") {
				console.info(`[Aaalice Subgraph Patch] Active (v${status.version})`);
				return;
			}
			const detail = status.state === "missing"
				? (chinese ? "请先安装并启用 ComfyUI-Aaalice-Nodes，然后重启 ComfyUI。"
					: "Install and enable ComfyUI-Aaalice-Nodes, then restart ComfyUI.")
				: (chinese ? "原节点包版本不兼容。请查看启动日志中的原因并更新补丁。"
					: "The node package version is incompatible. Check the startup log and update the patch.");
			console.error("[Aaalice Subgraph Patch]", detail, status.errors);
			app.extensionManager?.toast?.add({ severity: "warn",
				summary: chinese ? "快速组管理器子图补丁未生效" : "QuickGroupManager subgraph patch is inactive",
				detail, life: 15000 });
		} catch (error) {
			console.error("[Aaalice Subgraph Patch] Status check failed", error);
			app.extensionManager?.toast?.add({ severity: "error",
				summary: chinese ? "无法确认子图补丁状态" : "Could not check the subgraph patch",
				detail: chinese ? "请重启 ComfyUI，并在浏览器按 Ctrl+F5。"
					: "Restart ComfyUI and hard-refresh the browser (Ctrl+F5).", life: 15000 });
		}
	},
});
