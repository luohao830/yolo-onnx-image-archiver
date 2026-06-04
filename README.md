# YOLO ONNX WebUI 推理归档工具

这是一个基于 Gradio 的 WebUI 工具，用于批量运行 YOLO 系列 ONNX 模型，并按检测类别归档图片。项目只提供 WebUI 访问方式，适合在本机或 Docker 容器中处理大批量图片。

公开仓库不包含模型权重和业务图片数据。使用前需要自行准备 `.onnx` 模型和待处理图片。

## 功能

- 通过页面选择或上传 `.onnx` 模型。
- 通过页面上传图片，或直接选择 `images/` 下已有图片目录。
- 支持官方 COCO 类别和自训练模型类别文件。
- 支持按关注类别过滤检测结果。
- 将结果写入 `images/output/<run_id>/<类别>/images/`。
- 可选导出 YOLO txt 标签到 `labels/`。
- 可选输出画框图片到 `<类别>_画框/images/`。
- 可选将输出目录打包为 zip 供页面下载。
- 支持 GPU 优先推理，也可在页面切换为 CPU 推理。

## 目录结构

```text
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── images/
│   ├── uploads/
│   └── output/
├── models/
└── webui/
```

关键目录说明：

- `images/`：待处理图片和输出结果目录。
- `images/uploads/`：通过 WebUI 上传图片时的默认保存目录。
- `images/output/`：推理结果和 zip 输出目录。
- `models/`：放置 `.onnx` 模型和同名类别文件。
- `webui/`：Gradio 页面、推理任务管理和后处理代码。

## 准备模型和图片

将 ONNX 模型放入 `models/`：

```text
models/your_model.onnx
```

将图片放入 `images/` 下的任意子目录：

```text
images/example_set/
├── image_001.jpg
└── image_002.jpg
```

也可以启动 WebUI 后在页面中上传模型和图片。

## Docker 运行

容器内包含 CUDA 12 与 cuDNN 运行时，适合使用 `onnxruntime-gpu`。

构建并启动：

```bash
docker compose build
docker compose up -d
```

访问 WebUI：

```text
http://localhost:57860
```

默认 GPU 设备索引在 `docker-compose.yml` 中配置为 `["1"]`。如果机器只有一张显卡，通常需要改为 `["0"]`。

停止服务：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f app
```

## 本机运行

安装依赖：

```bash
pip install -r requirements.txt
```

启动 WebUI：

```bash
IMAGES_DIR=./images MODELS_DIR=./models python -m webui.app
```

默认监听：

```text
http://localhost:7860
```

如果不设置环境变量，程序默认使用：

- `IMAGES_DIR=/data/images`
- `MODELS_DIR=/data/models`

## 类别文件 sidecar

自训练模型建议提供同名类别文件，WebUI 会用于展示类别筛选项和输出目录名称。

支持以下格式：

- `model.names`：每行一个类别名。
- `model.txt`：每行一个类别名。
- `model.json`：`{"names": [...]}` 或 `[...]`。

示例：

```text
models/fire.onnx
models/fire.names
```

如果模型 ONNX metadata 中已经包含 `names`，程序会优先读取 metadata。

## 输出结构

一次推理会生成一个运行目录：

```text
images/output/20260604_153000/
├── person/
│   ├── images/
│   └── labels/
├── car/
│   ├── images/
│   └── labels/
└── no_detection/
    ├── images/
    └── labels/
```

说明：

- `images/` 下默认使用硬链接归档，避免重复占用大量磁盘空间。
- 如果页面关闭“必须硬链接”，硬链接失败时会回退为复制。
- `labels/` 仅在页面勾选“导出 YOLO txt 到 labels/”时写入。
- 画框图片仅在页面勾选“输出画框图片到 <类别>_画框”时写入。

## 公开仓库说明

本仓库刻意不提交以下内容：

- `.onnx` 模型权重。
- 原始图片数据。
- 推理输出目录。
- 临时压缩包和 Python 缓存。

如果需要发布可复现实验结果，建议在 GitHub Release、对象存储或内部文件服务器中单独管理模型权重和数据集。
