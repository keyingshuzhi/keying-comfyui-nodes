# Keying Batch Nodes（ComfyUI 批量加载/批量保存节点）

一套轻量、可移植的 ComfyUI 自定义节点：**从文件夹批量读图 → 批量保存输出**。  
适合电商抠图、白底合成、批量修图等工作流的“最后一公里”交付。

---

## 功能概览

本插件提供 2 个节点：

### ✅ Keying Batch Load Images (Folder)
- 从指定文件夹批量读取图片
- 支持递归扫描子目录
- 支持按文件名或修改时间排序
- 支持从指定下标开始加载（便于分批处理）
- 输出：
  - `images`：ComfyUI `IMAGE` **批次**（Batch），形状约为 `[B,H,W,3]`
  - `filenames`：文件名列表（用换行分隔的 `STRING`）

> 注意：ComfyUI 的 IMAGE batch 需要尺寸一致。该节点提供 `resize_mode` 用于处理尺寸不一致的输入。

### ✅ Keying Batch Save Images
- 将 `IMAGE` 批次批量保存到 ComfyUI 的 `output/` 下
- 默认按输入文件名保存（保留 basename）
- 支持输出到子目录（subfolder）
- 支持保存为 `jpg/png`
- 输出：
  - `saved_paths`：保存路径列表（换行分隔）

---

## 安装方式（macOS / Windows / Linux）

将节点放入 ComfyUI 的 `custom_nodes` 目录：

```
ComfyUI/
└─ custom_nodes/
   └─ keying_batch_nodes/
      └─ __init__.py
```

### 安装步骤

1) 创建目录
```bash
mkdir -p ComfyUI/custom_nodes/keying_batch_nodes
```

2) 将本插件代码保存为：
```bash
ComfyUI/custom_nodes/keying_batch_nodes/__init__.py
```

3) 重启 ComfyUI  
重启后在右键菜单搜索：
- `Keying Batch Load Images`
- `Keying Batch Save Images`

---

## 节点分类

节点分类位于：

- `Keying/Batch`

---

## 使用教程

### 1）批量输入 → 批量输出（最小示例）

1. 将待处理图片放到：
```
ComfyUI/input/batch_in/
```

2. 工作流连接：
```
Keying Batch Load Images (Folder)  ->  (你的处理链路)  ->  Keying Batch Save Images
```

3. 参数建议：
- Loader：
  - `folder`: `input/batch_in`
  - `resize_mode`: `resize_to_first`（默认，最省心）
- Saver：
  - `subfolder`: `white`
  - `format`: `jpg`
  - `quality`: `95`
  - `filenames`: 连接 Loader 的 `filenames`

输出将保存到：
```
ComfyUI/output/white/
```

---

### 2）同时输出两份：透明图 + 白底图（电商交付）

你可以放两个保存节点分别保存：

- 透明输出：
  - `subfolder = cutout`
  - `format = png`
- 白底输出：
  - `subfolder = white`
  - `format = jpg`

建议目录结构：
```
ComfyUI/output/cutout/
ComfyUI/output/white/
```

---

## 参数说明

### Keying Batch Load Images (Folder)

| 参数 | 说明 | 推荐 |
|---|---|---|
| folder | 输入文件夹路径（可相对 ComfyUI 根目录） | `input/batch_in` |
| recursive | 是否递归子目录 | `False` |
| max_images | 最大加载数量 | `9999` |
| start_index | 从第几张开始加载（0-based） | `0` |
| sort | 排序方式（name/mtime asc/desc） | `name_asc` |
| resize_mode | 尺寸策略：自动统一尺寸或严格一致 | `resize_to_first` |

`resize_mode` 解释：
- `resize_to_first`：将所有图片缩放到第一张图尺寸（批处理最稳）
- `no_resize_require_same`：不缩放，但要求所有图片尺寸完全一致，否则报错

---

### Keying Batch Save Images

| 参数 | 说明 | 推荐 |
|---|---|---|
| images | 输入 IMAGE batch | 必填 |
| subfolder | 输出子目录（相对 ComfyUI/output） | `white` / `cutout` |
| format | `png` 或 `jpg` | 白底用 `jpg`，透明用 `png` |
| quality | jpg 质量（1-100） | `95` |
| prefix | 文件名前缀（可选） | 空 |
| filenames | 可选：原文件名列表（换行分隔） | 建议接 Loader 输出 |

命名逻辑：
- 若提供 `filenames`：使用对应的原文件名（去掉扩展名）保存
- 若未提供：使用序号 `00000, 00001...` 保存

---

## 常见问题（FAQ）

### Q1：为什么要 resize？
ComfyUI 的 `IMAGE batch` 需要统一尺寸才能堆叠成一个 batch。  
如果你的输入尺寸不一致，推荐使用 `resize_to_first`，这样批处理不会中断。

### Q2：输出路径在哪里？
所有输出都在 ComfyUI 的：
```
ComfyUI/output/<subfolder>/
```

### Q3：能不能保留 alpha（透明通道）？
本节点保存的是 ComfyUI 的 `IMAGE`（RGB）。  
如果你的工作流最终输出是“带透明的 RGBA”，需要在进入本保存节点前先转换为可保存的格式，或扩展保存节点以支持 RGBA。

---

## License
按你的项目需要补充（MIT / Apache-2.0 / 私有等）。
