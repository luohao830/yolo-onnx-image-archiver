# 简化版：ONNXRuntime-GPU 推理 + 按类别硬链接归档

只做一件事：用 `.onnx` 模型推理图片，取 top1 类别，把图片硬链接到 `输出目录/类别/`。

## 依赖

```bash
pip install -r requirements.txt
```

需要环境支持 GPU：安装好 NVIDIA 驱动 + CUDA（以及 onnxruntime-gpu 对应版本）。

## 使用

```bash
python infer_link.py \
  --model /path/to/model.onnx \
  --images /path/to/images \
  --out /path/to/output \
  --recursive \
  --batch 16 \
  --conf 0.25
```

- 如果你的 ONNX 模型输入是固定尺寸/固定 batch（比如 `1x3x1280x1280`），脚本会自动读取并强制使用对应的 `imgsz/batch`（你也可以手动指定 `--batch 1 --imgsz 1280`）。
- 无检测会归入 `no_detection/`
- 硬链接失败会自动回退复制；如果你不想回退复制，加 `--no-copy-fallback`

## 使用（容器，推荐）

容器内已包含 CUDA12 + cuDNN9 运行时库，适合 `onnxruntime-gpu` 直接启用 GPU。

1) 准备目录（宿主机）：

- `./images`：待处理图片
- `./models`：`*.onnx` 模型
- `./images/output`：输出目录（会生成 `images/output/<label>/...`，并且与图片同一文件系统，硬链接才能生效）

2) 构建并运行：

```bash
docker compose build
docker compose up -d
docker compose exec infer bash
```

进入容器后手动执行：

```bash
python3 /app/infer_link.py \
  --model /data/models/model.onnx \
  --images /data/images \
  --out /data/output \
  --recursive
```

如果你的机器只有一张卡或想换卡，修改 `docker-compose.yml` 里的 `device_ids`（例如 `["0"]`）。

## 类别名（可选）

优先从 ONNX metadata 的 `names` 读取；如果你的 onnx 没带 names，可以放同名 sidecar：

- `model.names`：每行一个类别名
- `model.json`：`{"names":[...]}` 或 `[...]`

python infer_link.py --model ./models/fire-1204.onnx --images ./smoke-00434/images/ --out ./smoke-00434/out --recursive --batch 16 --conf 0.25
