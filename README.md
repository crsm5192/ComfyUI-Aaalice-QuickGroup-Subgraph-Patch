# ComfyUI Aaalice 快速组管理器子图补丁

修复 [ComfyUI-Aaalice-Nodes](https://github.com/Aaalice233/ComfyUI-Aaalice-Nodes) 的 **⚡ 快速组管理器** 无法发现、控制和定位原生子图内 group 的问题。

**v1.1.0 起是可直接安装的 ComfyUI 扩展包**，支持绘世启动器从 GitHub 地址安装，也支持 ComfyUI-Manager 的 Install via Git URL。安装后随 ComfyUI 自动加载，无需运行补丁命令。

本扩展依赖已安装并启用的 `ComfyUI-Aaalice-Nodes`，不新增节点，不增加 Python 依赖。它在 ComfyUI 提供前端脚本时加载修正版本，**不改写原节点包文件**。停用或删除本扩展并重启后，原包自动恢复原来的行为。

## 安装

### 绘世启动器 / ComfyUI-Manager

1. 先安装并启用 `ComfyUI-Aaalice-Nodes`。
2. 在启动器的扩展安装页面，或 ComfyUI-Manager 的 **Install via Git URL** 中，填写：

   ```text
   https://github.com/crsm5192/ComfyUI-Aaalice-QuickGroup-Subgraph-Patch
   ```

3. 安装完成后重启 ComfyUI，在浏览器按 **Ctrl+F5**。

如果之前安装失败，请刷新启动器的仓库信息，再用同一地址重新安装。若启动器遗留了不完整的补丁目录，请先通过启动器移除该失败项再重装。

### 手动安装

在 ComfyUI 的 `custom_nodes` 目录克隆仓库即可，无需运行 `patch.py`：

```powershell
cd "D:\Softwares\ComfyUI\ComfyUI\custom_nodes"
git clone https://github.com/crsm5192/ComfyUI-Aaalice-QuickGroup-Subgraph-Patch.git
```

安装后的目录应为：

```text
custom_nodes/
├── ComfyUI-Aaalice-Nodes/
└── ComfyUI-Aaalice-QuickGroup-Subgraph-Patch/
    ├── __init__.py
    ├── extension.py
    ├── requirements.txt
    ├── pyproject.toml
    ├── web/extension.js
    ├── payload/quick_group_manager_subgraphs.js
    └── patch.py
```

随后重启 ComfyUI，并在浏览器按 **Ctrl+F5**。Python 版本要求为 3.10+，直接使用 ComfyUI 自带的 Python 即可。

## 修复行为

- 从管理器所在图递归扫描所有后代子图；放在子图内的管理器只管理该层及其后代。
- 当前层 group 保留原编号，原有排序和联动规则继续使用。
- 子图 group 使用子图 UUID 和 group 编号组合标识，避免不同图内相同编号互相覆盖。
- 列表、联动编辑器显示 `子图 / 更深子图 / group` 路径。
- 开关、静音/绕过、颜色过滤、排序、联动、预设恢复使用真实子图节点。
- 定位按钮先打开 group 所属子图，再定位原生 group 的边界。
- 子图中的操作使用根工作流事务，并刷新根图与子图内已挂载的管理器控件。

多个子图节点引用同一份子图定义时，列出一次，显示第一条发现的路径；开关作用于该共享定义的所有引用。这与 ComfyUI 原生子图的共享节点模式一致。

## 状态、更新与卸载

浏览器打开工作流后，ComfyUI 日志中出现 `Active / 子图补丁已启用` 表示补丁已生效。也可在 ComfyUI 地址后打开 `/aaalice-quickgroup-subgraph-patch/status`，确认 `state` 为 `active`。

若原节点包未启用，或其更新后的代码不兼容，扩展会在日志和界面中提示原因，不替换不兼容的脚本。请启用原包，或更新本补丁后重启 ComfyUI。

通过启动器 / Manager 更新本扩展即可。卸载时在启动器中停用或删除本补丁，然后重启 ComfyUI 并按 **Ctrl+F5**；原节点包无需恢复文件。

### 从 v1.0 手动补丁迁移

如果之前执行过 `patch.py install`，请先关闭 ComfyUI，再使用原来的工具卸载手动补丁：

```powershell
python patch.py uninstall --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
```

然后按上面的方式安装扩展。扩展也可以识别完整且未修改的旧补丁，但仅删除扩展不会移除旧版已经写入的补丁；因此建议先完成上述迁移。

`patch.py` 继续保留 `check / install / uninstall`，用于旧版维护。普通扩展安装无需使用它。旧工具的备份位于原包 `.aaalice-quickgroup-subgraph-patch/`；若原包被手动编辑或更新，卸载工具会保留改动并拒绝直接覆盖，请根据备份合并或恢复。

## 验证与兼容性

已验证原节点包提交 `2395128e6f02d60ccc4c2b514201533cd8fd3f92`，并核对当前本机 ComfyUI 的扩展加载、静态脚本路径和安全中间件顺序。

共 **56 项自动测试**：12 项扩展安装和 HTTP 加载测试、8 项旧安装工具测试、6 项子图辅助模块测试，以及在原包临时副本上运行的 30 项回归测试。覆盖启动加载顺序、脚本地址、停用恢复、不修改原文件、缺失和不兼容原包、旧补丁兼容，以及多层子图、开关、联动、排序、预设与导航。完整浏览器交互仍需结合实际工作流确认。

```powershell
# 使用带有 aiohttp 的 ComfyUI Python；例如绘世的 python\python.exe
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/subgraphs.test.js
node --check web/extension.js
python tests/verify_target.py --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
```

测试仅使用临时目录，不修改指定节点包。GitHub Actions 自动运行扩展和旧工具测试；原包回归验证需要本地原包源码。

## 许可

MIT。原节点包作者为 Aaalice233；本项目保留原作者许可声明。
