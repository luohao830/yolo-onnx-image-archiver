# 项目架构文档：基于 YOLOv5 与 FiftyOne 的大规模图像检索系统

## 1. 项目概述

本项目旨在构建一个基于 Docker 的高性能本地图像/视频推理与检索服务。利用服务器强大的 GPU 算力（RTX 4090），通过 YOLOv5 进行目标检测，并将结果导入 FiftyOne 进行可视化管理和检索。用户通过 Gradio WebUI 进行交互控制。

### 核心目标

- **自动化推理**：对指定目录下的海量图片/视频进行批量 YOLOv5 推理。
- **可视化检索**：利用 FiftyOne 提供的高级界面，根据检测到的物体（标签）、置信度等进行筛选和查看。
- **硬件隔离**：指定使用服务器的特定 GPU（Index 1）运行，互不干扰。
- **持久化存储**：确保 Dataset 和 MongoDB 数据在容器重启后不丢失。

## 2. 系统架构

系统由三个核心 Docker 服务和一套 Python 业务逻辑组成。

### 2.1 容器服务架构 (Docker Compose)

1. **MongoDB (`mongo:5.0`)**:
   - **职责**: 存储 FiftyOne 的数据集元数据（Metadata）、标签（Labels）、检测框（Bounding Boxes）。
   - **配置**: 限制 WiredTiger 缓存为 1GB，防止内存溢出。
2. **应用容器 (`app`)**:
   - **基础镜像**: `ultralytics/yolov5:v7.0` (PyTorch环境)。
   - **附加组件**: FiftyOne, Gradio。
   - **硬件资源**: 映射 GPU 1，开启 16GB 共享内存 (`shm_size`)。
   - **端口**:
     - `5151`: FiftyOne App (可视化界面)。
     - `7860`: Gradio WebUI (控制台)。

### 2.2 Python 业务逻辑分层

为了保证代码的可维护性，业务代码将分为三层：

1. **UI 层 (`app.py`)**:
   - 基于 Gradio 构建。
   - 负责接收用户指令（输入路径、选择模型、设置数据集名称）。
   - 显示实时日志和进度。
   - 提供跳转到 FiftyOne 的链接。
2. **处理层 (`processing.py`)**:
   - **YOLO 推理引擎**: 封装 `torch.hub` 或 `detect.py` 逻辑，支持批量推理。
   - **数据清洗**: 过滤低置信度结果，转换坐标格式（YOLO xywh -> FiftyOne xywh）。
3. **工具层 (`utils.py`)**:
   - 封装日志、路径扫描、配置读取等辅助能力。
   - 与 MongoDB/FiftyOne 交互的通用方法集中于此，供 `processing.py` 调用（例如创建/加载 Dataset、批量写入 Samples）。

## 3. 目录结构设计

宿主机与容器内的目录映射关系如下：

```
Project_Root/
├── docker-compose.yml       # 容器编排
├── Dockerfile               # 镜像构建
├── fo_data/                 # [映射] MongoDB 数据持久化目录
├── images/                  # [映射] 待处理的图片/视频数据集根目录
├── models/                  # [映射] 存放 .pt 模型文件 (yolov5s.pt, custom.pt)
├── webui/                   # [映射] Python 源代码目录
│   ├── app.py               # 程序入口 (Gradio)
│   ├── processing.py        # 推理与数据处理核心逻辑
│   └── utils.py             # 工具函数 (日志、路径扫描)
└── scripts/                 # [映射] 临时脚本
```

## 4. 核心功能流程 (Workflow)

### 阶段一：初始化

1. 启动 Docker 容器。
2. FiftyOne App 在后台启动（监听 5151）。
3. Gradio App 在前台启动（监听 7860）。

### 阶段二：用户操作 (Gradio)

1. **输入设置**:
   - **数据集名称**: 例如 "korean_traffic_2023"。
   - **图片路径**: 例如 `/dataset/raw_images` (容器内路径)。
   - **模型选择**: 下拉选择 `/models` 目录下的 `.pt` 文件。
   - **置信度阈值**: Slider (0.1 - 0.9)。
2. **点击 "开始处理"**:
   - 系统扫描目录下所有图片格式文件。
   - **增量检查**: 如果图片已存在于 Dataset 中，选择跳过或覆盖。
3. **处理中 (Batch Processing)**:
   - 加载 YOLO 模型到 GPU 1。
   - 分批次（Batch Size）读取图片。
   - 执行推理 -> 获取 Bbox 和 Label。
   - 将结果转换为 FiftyOne Sample 对象。
   - 写入 MongoDB。
   - Gradio 界面更新进度条。

### 阶段三：结果浏览

1. 处理完成后，Gradio 提示 "导入完成"。
2. 用户点击链接访问 `http://<server-ip>:5151`。
3. 在 FiftyOne 界面中通过 SQL-like 语法查询（例如：`Label == 'person' & Confidence > 0.8`）。

## 5. 关键技术细节与约束

1. **内存管理**:
   - 不能一次性将所有图片读入内存。必须使用 **生成器 (Generator)** 模式，读一批、推一批、存一批。
2. **坐标转换**:
   - YOLO 输出: `[x_center, y_center, width, height]` (归一化 0-1)。
   - FiftyOne 需要: `[top-left-x, top-left-y, width, height]` (归一化 0-1)。
   - **必须在代码中进行转换，否则框的位置会偏。**
3. **并发锁**:
   - MongoDB 对并发写入敏感，尽量单线程写入 FiftyOne Dataset，或者使用 FiftyOne 的 `dataset.add_samples()` 批量写入接口。

## 6. 待确认项 (To-Do)

- **视频处理**: 目前优先支持图片。视频需要抽帧处理，是否需要在此版本加入？(建议 V1.0 仅支持图片，V1.5 加入视频抽帧)。
- **模型来源**: 默认使用 `yolov5s.pt`，是否需要自动下载其他模型？
