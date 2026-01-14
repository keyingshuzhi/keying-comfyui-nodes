# keying-comfyui-nodes

Keying 自研的 ComfyUI 节点套件，面向电商与批量图像处理工作流，提供 **精准抠图（IMAGE+MASK）/ 批量加载保存 / 自动尺寸纯色画布（预设色+Custom RGB）** 等能力，帮助你把“能出图”升级为“可交付生产线”。

---

## 功能一览

### 1) Keying Remove Background (rembg)
- ✅ 精准抠图：输出 **IMAGE（前景）+ MASK（Alpha）**
- ✅ 支持 Batch 输入
- ✅ 可选输出白底（white_bg）
- ✅ **本地模型目录加载（不使用 ~/.u2net）**：强制从 `models/u2net/` 读取

> 适合：商品抠图、边缘可控修边（Grow/Feather）、白底主图/场景合成前置处理

### 2) Keying Batch Nodes
- ✅ Batch Load：从文件夹批量读取图片（排序/递归/起始索引/最大数量）
- ✅ Batch Save：按原文件名批量保存到 `output/<subfolder>/`（支持 jpg/png）
- ✅ 面向交付：透明图/白底图可分目录输出

> 适合：上新批量处理、代运营交付、素材整理

### 3) Keying Solid Canvas (Auto Size)
- ✅ 纯色画布：可自动跟随参考图像尺寸（H/W）
- ✅ 内置常用背景色预设（棚拍灰/纯白/暖白/灰阶等）
- ✅ Custom RGB：仅当 preset 选为 `(Custom RGB)` 时 r/g/b 生效
- ✅ 支持 Batch 输出（可跟随参考图 batch 数）

> 适合：白底/灰底背景生成、批量合成更稳

---

## 目录结构（建议）

你可以按这个结构组织仓库与节点目录（也方便 ComfyUI-Manager/手动安装）：

```
keying-comfyui-nodes/
  README.md
  LICENSE
  nodes/
    keying_rembg/
      __init__.py
      README.md
    keying_batch_nodes/
      __init__.py
      README.md
    keying_canvas_color/
      __init__.py
      README.md
  models/
    u2net/
      isnet-anime.onnx
      isnet-general-use.onnx
      u2net.onnx
      u2netp.onnx
  examples/
    workflows/
```

---

## 安装方式

### 方式 A：手动安装（推荐给开发/可控）

1) 克隆仓库：
```bash
git clone https://github.com/<your_org_or_name>/keying-comfyui-nodes.git
```

2) 把节点目录放到 ComfyUI 的 `custom_nodes/` 下（二选一）：

- **选项 1：整个仓库放进去（方便更新）**
  ```
  ComfyUI/custom_nodes/keying-comfyui-nodes/
  ```
- **选项 2：只拷贝 nodes 下的子目录**
  ```
  ComfyUI/custom_nodes/keying_rembg/
  ComfyUI/custom_nodes/keying_batch_nodes/
  ComfyUI/custom_nodes/keying_canvas_color/
  ```

3) 重启 ComfyUI

---

## 依赖说明

- `keying_canvas_color`：仅依赖 `numpy`（ComfyUI 通常自带）
- `keying_batch_nodes`：`numpy`、`Pillow`（通常 ComfyUI 环境已具备；如缺再装）
- `keying_rembg`：依赖 `rembg` + `onnxruntime`

如需安装 rembg（在 ComfyUI venv 内执行）：
```bash
cd /path/to/ComfyUI
source .venv/bin/activate
pip install rembg onnxruntime
```

---

## 模型放置（重要）

`Keying Remove Background (rembg)` 采用 **本地模型目录优先**（不使用 `~/.u2net`），请把模型放到：

```
<ComfyUI>/models/u2net/
  isnet-anime.onnx
  isnet-general-use.onnx
  u2net.onnx
  u2netp.onnx
```

缺文件会直接报错并提示放置路径（避免自动下载、保证可复现/便携）。

---

## 推荐工作流（电商交付版）

目标：一次跑完输出两套交付文件：
- `output/cutout/`（透明/前景）
- `output/white/`（白底主图）

推荐链路：
1. Batch Load（从 `input/batch_in/` 读图）
2. Keying Remove Background（输出 image + mask）
3. mask 修边：GrowMask（扩/缩） + Feather（羽化）
4. Keying Solid Canvas（自动尺寸 + 预设背景色）
5. 合成：ImageCompositeMasked（destination=画布，source=前景，mask=修边后mask）
6. Batch Save 两路：cutout 保存前景，white 保存白底结果

参数提示：
- 去白边：`expand=-1~-2`
- 补漏抠：`expand=+1`
- 羽化：`0.5~1.5`

---

## 常见问题（FAQ）

### 1) Prompt has no outputs
如果你自研的 Save 节点不被识别为输出节点，需要在节点类里加：
```python
OUTPUT_NODE = True
```
并重启 ComfyUI。

### 2) rembg 报 PIL 类型错误 / 形状异常
避免使用 `numpy().squeeze()` 直接转 PIL（会把 H/W=1 挤掉）。本套件的 Keying rembg 节点已做“只去 batch 维”的健壮转换。

### 3) 批量输入尺寸不一致
ComfyUI 的 batch 通常要求尺寸一致。建议在 Batch Load 时统一尺寸（resize_to_first 或固定尺寸策略）。
