# 项目架构文档：轻量化多模型打标与导出系统（ONNXRuntime-GPU）

## 1. 最新需求（以此为准）

你当前的真实需求不是“训练/完整 YOLOv5 环境”，而是面向海量采集图片的**轻量推理+管理**：

- **推理后端唯一**：仅使用 `onnxruntime-gpu`（不再支持 `.pt`/PyTorch 推理），模型文件为 `.onnx`
- **多模型分次推理**：同一批图片可用不同模型分批推理，结果**叠加**到同一套标签体系里
- **默认 top1**：每张图取最高置信度检测类别作为该模型的标签；无检测打 `no_detection`
- **纯 Web 管理**：不使用 CLI；Web 页面负责同步/推理/浏览/导出
- **按标签浏览**：Web 中可选择某个标签查看图片列表/缩略图
- **导出为 ZIP**：按标签导出 ZIP，带进度条；导出过程使用**硬链接 staging** 来节省空间（同一文件系统时生效，失败自动回退复制）
- **整体轻量化**：移除 `ultralytics/yolov5` 镜像和 PyTorch 依赖；减少服务数量与启动成本

## 2. 为什么之前代码在 `webui/`

历史原因是 docker-compose 将 `./webui` 作为“UI 代码挂载点”来热更新，便于快速迭代 Gradio/FiftyOne。  
但随着需求升级为“完整的轻量化平台”，把所有逻辑都堆在 `webui/` 会导致：职责混乱、可测试性差、后端难替换（例如从 PyTorch 切 ONNX）。

因此本次重构目标是：

- `webui/` 只保留**Web UI 入口/展示层**
- 核心能力拆分为独立模块（索引、推理、存储、导出、任务管理），便于替换与扩展

## 3. 新架构（模块化）

### 3.1 组件

- **Web UI（Gradio）**：发起“同步/推理/导出”任务；浏览标签、预览图片
- **任务执行器**：串行执行耗时任务（避免 GPU/IO 争用），提供进度与状态
- **元数据存储（SQLite）**：保存图片清单、模型、每次推理结果（按模型维度）、导出记录
- **推理引擎（ONNXRuntime-GPU）**：加载 `.onnx`，做预处理/推理/NMS/后处理，输出检测与 top1 标签

> 注：为了轻量化，默认不再依赖 MongoDB/FiftyOne；如未来确实需要高级可视化，再作为可选插件加入。

### 3.2 数据模型（建议）

- `images(path UNIQUE, added_at, width, height, ...)`
- `models(model_id UNIQUE, onnx_path, imgsz, class_names, ...)`
- `runs(run_id, model_id, started_at, ended_at, conf, status, error)`
- `predictions(image_id, model_id, run_id, label, confidence, created_at)`（每图每模型默认一条 top1；无检测为 `no_detection`）

### 3.3 标签语义（便于筛选与导出）

- **聚合标签**：跨模型汇总后的标签列表（例如 `person`、`device`、`no_detection`）
- **模型标签**：同一标签在不同模型下的归因（例如 `person_v1:person`）

## 4. 目录结构（重构后）

```
Project_Root/
├── docker-compose.yml
├── Dockerfile
├── images/                  # 输入媒资（不移动）
├── models/                  # 仅存放 .onnx（.pt 不再用于推理）
├── data/                    # SQLite、导出产物等（新增）
├── app/                     # 后端核心模块（索引/推理/导出/存储/任务）
└── webui/                   # 纯 UI 入口（调用 app/ 提供的能力）
```

## 5. 核心流程（纯 Web）

1. **同步**：扫描 `/images`（可递归）个 `.onnx` 模型（`model_id`），对未处理（或选择覆盖）的图片推理，写入 `predictions`，增量写入 SQLite（仅新增，不删除）
2. **推理打标**：选择一
3. **按标签浏览**：选择标签（可选模型维度），展示对应图片缩略图/列表
4. **导出 ZIP**：按标签收集图片，staging 目录优先硬链接，再压缩为 ZIP，提供下载

## 6. 非目标（本阶段不做）

- 训练/微调、模型下载器、视频抽帧
- TensorRT 引擎生成（后续可加，但默认先稳的 ONNXRuntime-GPU）
