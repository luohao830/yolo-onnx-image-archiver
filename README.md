# YOLO ONNX WebUI 推理归档工具

基于 Gradio 的单机 YOLO ONNX 推理与归档工具：上传或选择模型、上传图片或 `.zip` 压缩包、选择关注类别，运行推理并按类别归档，支持画框与 YOLO `labels/txt` 导出，推理完成后一键打包（`zip -r -0`，不压缩）下载。

## 功能

- 模型管理：上传 `.onnx`、刷新模型列表、按模型 sidecar（`.names`/`.txt`/`.json`）加载类别名。
- 图片输入：直接上传图片，或上传 `.zip` 压缩包（后台自动解压仅保留受支持图片，并自动回填图片目录）。
- 图片目录：支持相对 `images/` 的子路径，也支持宿主机绝对路径（需与挂载目录一致）。
- 推理参数：置信度 `conf`、NMS `iou`、`batch`、`imgsz`、递归扫描、硬链接/复制回退、预处理线程、预取 batch、`use_cpu`、画框、导出 `txt`、未命中目录名。
- 关注类别：官方 COCO 80 类多选，或自训练模型按 sidecar 加载类别多选。
- 进度反馈：推理进度条与打包进度条**相互独立**；推理完成后打包条接管显示。
- 多 GPU：按可见 GPU 数量自动创建多个 worker 进程，任务级多 GPU 分流加速；单 GPU / 无 GPU 自动回退，无需手动配置。
- 结果下载：推理结束后可勾选“推理结束后打包 zip（-0 不压缩）并下载”，产出的 `zip` 采用 `ZIP_STORED`（等价 `zip -r -0`，只打包不压缩），可直接在界面下载。
- 时区：容器设为 `Asia/Shanghai`（UTC+8），日志与新建目录时间戳均使用本地时间。

## 目录结构

```text
.
├── webui/                 # Gradio 页面、推理内核、任务管理、worker、解压、后处理
├── images/                # 图片与输出工作区（运行产物，不入库）
├── models/                # .onnx 模型与 sidecar（权重不入库，仅示例 sidecar）
├── tests/webui/           # webui 纯函数测试
├── Dockerfile             # 单容器 Gradio 镜像，入口 python3 -m webui.app
├── docker-compose.yml     # 单服务 webui，暴露 7860，挂载 NVIDIA GPU
└── requirements.txt       # numpy / opencv-python-headless / onnxruntime-gpu / gradio
```

## 准备模型和图片

1. 将 `.onnx` 模型放入 `models/`（可附带同名 `.names`/`.txt`/`.json` 说明类别名）。
2. 将待推理图片放入 `images/` 下某个目录，或直接在 WebUI“上传图片”页上传图片/`.zip`。

## Docker 运行

```bash
mkdir -p models
docker compose build
docker compose up -d
```

访问：

```text
http://127.0.0.1:7860/
```

`docker-compose.yml` 默认仅挂载 GPU 0。如需启用任务级双 GPU 分流，把：

```yaml
device_ids: ["0"]
```

改为：

```yaml
device_ids: ["0","1"]
```

宿主机路径挂载：`docker-compose.yml` 中 images 挂载与 `HOST_IMAGES_DIR` 使用同一个环境变量 `IMAGES_HOST_DIR` 统一控制（默认回退 `/tmp/yolo_images`，开箱测试用；生产环境务必覆盖）。设置 `IMAGES_HOST_DIR` 为宿主机存放图片的实际绝对路径（与挂载目标 `/data/images` 指向同一个目录）后，WebUI 会用它把用户输入的宿主机绝对路径换算为容器内 `/data/images` 下的路径，从而正确读取。例如：`IMAGES_HOST_DIR=/home/luohao/myimgs docker compose up -d`。

验证 GPU：

```bash
docker compose exec webui python3 -c "import onnxruntime as ort;print(ort.get_available_providers())"
```

输出应包含 `CUDAExecutionProvider`。

## 本机运行

```bash
python -m pip install -r requirements.txt
python -m webui.app
```

默认监听 `http://0.0.0.0:7860`。环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `IMAGES_DIR` | `/data/images` | 容器内图片工作区 |
| `HOST_IMAGES_DIR` | 同 `IMAGES_DIR` | 宿主机侧 images 路径，用于绝对路径换算 |
| `MODELS_DIR` | `/data/models` | 模型目录 |
| `TZ` | `Asia/Shanghai` | 时区 |

## 类别文件 sidecar

放在 `models/` 下与模型同名：
- `.names` 或 `.txt`：每行一个类别名。
- `.json`：`{"names": ["..."]}` 或直接的字符串数组。

无 sidecar 时使用类别 `cls_id` 作为类别名。

## 输出结构

推理结果写入 `images/output/<run_id>/`：

```text
output/<run_id>/
├── <类别>/images/        # 命中的原图（硬链接/复制）
├── <类别>/labels/        # YOLO txt（开启 save_txt 时）
└── <类别>_画框/          # 画框图片（开启 draw_boxes 时）
```

未命中类别的图片归入“未命中目录名”（默认 `no_detection`）。打包产物为 `output/<run_id>.zip`（`zip -r -0`，不压缩）。

## 测试

```bash
python -m pytest tests/webui -v
```

## 公开仓库说明

仓库不包含 `.onnx` 模型权重与业务图片。`images/` 仅保留目录占位，`models/*.onnx` 被忽略，使用者自行放入模型。