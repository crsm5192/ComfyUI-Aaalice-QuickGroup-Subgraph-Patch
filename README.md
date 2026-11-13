# ComfyUI Aaalice 快速组管理器子图补丁

修复 [ComfyUI-Aaalice-Nodes](https://github.com/Aaalice233/ComfyUI-Aaalice-Nodes) 的 **⚡ 快速组管理器** 无法发现、控制和定位原生子图内 group 的问题。

这是独立的补丁项目，包含安装工具和前端补丁。**不是直接放入 `custom_nodes` 就会自动加载的节点包**。安装工具只修改原包的两个前端文件，并新增一个辅助模块，不增加 Python 依赖，也不新增节点。

## 修复行为

- 从管理器所在图递归扫描所有后代子图；放在子图内的管理器只管理该层及其后代。
- 当前层 group 保留原编号，原有排序和联动规则继续使用。
- 子图 group 使用子图 UUID 和 group 编号组合标识，避免不同图内相同编号互相覆盖。
- 列表、联动编辑器显示 `子图 / 更深子图 / group` 路径。
- 开关、静音/绕过、颜色过滤、排序、联动、预设恢复使用真实子图节点。
- 定位按钮先打开 group 所属子图，再定位原生 group 的边界。
- 子图中的操作使用根工作流事务，并刷新根图与子图内已挂载的管理器控件。

多个子图节点引用同一份子图定义时，列出一次，显示第一条发现的路径；开关作用于该共享定义的所有引用。这与 ComfyUI 原生子图的共享节点模式一致。

## 安装（Windows）

要求 Python 3.10+。关闭 ComfyUI 后，在 PowerShell 中执行：

```powershell
cd C:\Project\ComfyUI-Aaalice-QuickGroup-Subgraph-Patch
python patch.py check --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
python patch.py install --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
```

随后启动 ComfyUI，在浏览器按 **Ctrl+F5**。其他安装位置请替换 `--target`。

原文件备份位于目标节点包的 `.aaalice-quickgroup-subgraph-patch/`，包含原文件和 SHA-256 校验记录。重复安装不会重复打补丁；无法识别的源代码会在写入前报错。备份目录应保留到卸载完成。

## 检查与卸载

```powershell
python patch.py check --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
python patch.py uninstall --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
```

卸载恢复原文件的完整字节内容并删除新增模块。安装后如果原文件被更新或手动修改，工具会拒绝覆盖这些改动；请保留现有文件，再根据备份手动合并或恢复。**更新原节点包前先卸载补丁**，更新后重新执行 `check`。

修改范围：

| 文件 | 修改用途 |
| --- | --- |
| `js/lib/quick_group_manager_runtime.js` | 扫描后代子图、使用根工作流事务、刷新各层控件 |
| `js/lib/group_navigation.js` | 导航到 group 所属图并使用原生边界 |
| `js/lib/quick_group_manager_subgraphs.js` | 新增扫描、组标识和导航辅助模块 |

## 验证

已验证原节点包提交 `2395128e6f02d60ccc4c2b514201533cd8fd3f92`。共 **44 项自动测试**通过：6 项子图辅助模块测试、8 项安装工具测试，以及在原包临时副本上运行的 30 项回归测试，其中包含 7 项新增子图回归测试。临时副本验证不会修改指定节点包。

```powershell
node --test tests/subgraphs.test.js
python -m unittest discover -s tests -p "test_*.py" -v
python tests/verify_target.py --target "D:\Softwares\ComfyUI\ComfyUI\custom_nodes\ComfyUI-Aaalice-Nodes"
```

测试覆盖多层子图、重复编号、共享定义与循环引用、真实节点引用、跨层联动、颜色过滤、排序、静音/绕过、预设恢复、空缓存恢复、导航、重复安装、逐字节卸载、写入失败回滚和用户改动保护。浏览器内的完整交互仍需在实际 ComfyUI 工作流中确认。

## 许可

MIT。原节点包作者为 Aaalice233；本项目保留原作者许可声明。
