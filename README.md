# YOLO 多用户推理平台

本仓库正在从单机 Gradio 推理工具演进为多用户 YOLO 推理平台。当前主线由 FastAPI 后端、内置管理员后台的 React 前端和 Nginx 统一入口组成；旧版 `webui/` 仍保留为推理内核与调试入口。

## 当前能力

- `backend/`：FastAPI API 服务，提供公开任务创建、人员筛选上传入队、状态/日志查询、结果下载、模型管理、并发配置、任务监控、详情、取消、重试与下载接口。
- `frontend/user-app/`：用户前台，内置 `/admin/` 管理后台，包含上传工作台、任务进度/关键日志/结果下载视图、模型管理、系统配置和任务监控页面。
- `gateway/`：Nginx 统一入口，将用户前台、管理员后台和 `/api/` 转发到同一端口。
- `webui/`：旧版 Gradio 工具链与 `webui.processing.run_inference` 推理实现，后端 `TaskRunner` 通过适配层复用它。

当前阶段已经打通人员筛选与高级模式的任务创建、图片/压缩包上传、归档解压、任务入队、状态/关键日志与 SSE 实时事件查询、逐图检测结果与结果图片获取、已完成任务结果下载链路。高级模式已支持 `model_id` 与 `payload`（conf/iou/batch/imgsz/draw_boxes/save_txt 等，服务端 normalize 合并默认值）创建任务并上传文件入队。

## 目录结构

```text
.
├── backend/                 # FastAPI、数据库模型、服务层、仓储层、worker 基础能力
├── frontend/
│   └── user-app/            # 用户前台与内置管理员后台，Vite + React
├── gateway/                 # Docker Compose 统一入口 Nginx 配置
├── images/                  # 旧版 webui 默认图片目录，当前 Compose 不挂载
├── models/                  # 模型文件目录，Docker 中挂载为 /data/models
├── runtime/                 # 运行时工作区，保存 SQLite、上传文件、任务和结果产物
├── tests/backend/           # 后端单元测试与 API smoke 测试
└── webui/                   # 旧版 Gradio UI、推理处理与 worker 代码
```

`runtime/`、`models/*.onnx`、压缩包和前端构建产物默认不提交。

## Docker Compose 启动

启动前准备运行目录：

```bash
mkdir -p models runtime
```

后端容器默认申请宿主机全部 NVIDIA GPU。宿主机需要已安装 NVIDIA 驱动和 NVIDIA Container Toolkit，并确保以下命令能看到 GPU：

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 nvidia-smi
```

构建并启动：

```bash
docker compose build
docker compose up -d
```

当前 `docker-compose.yml` 会启动 3 个容器：

- `backend`：FastAPI 后端，容器内监听 `8000`
- `user-app`：用户前台和内置管理员后台静态站点
- `gateway`：统一入口 Nginx，对宿主机暴露 `58000`

访问地址：

```text
http://127.0.0.1:58000/
```

路由分发：

- `/`：用户前台
- `/admin/`：由用户前台静态站点承载的内置管理员后台
- `/api/...`：后端 API

gateway 默认允许最大 `100g` 请求体，用于人员筛选模式上传图片或压缩包；后端同步按上传原始文件大小限制为 100G，不再按解压后的图片数量或总大小限制。`.zip` 压缩包每次都会重新上传到当前任务目录并解压，不做 hash 复用或服务端压缩包缓存。gateway 访问日志使用不含 query string 的自定义格式，避免 `access_token` 或短期 SSE token 落盘。

常用命令：

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f gateway
docker compose down
```

GPU 验证：

```bash
docker compose exec backend nvidia-smi
docker compose exec backend python3 -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

`onnxruntime` 输出应包含 `CUDAExecutionProvider`。如需固定使用特定 GPU，可在 `docker-compose.yml` 的 `backend.deploy.resources.reservations.devices` 中将 `count: all` 改为 `device_ids: ["0"]`，不要同时设置 `count` 和 `device_ids`。

如果启动后端容器时报 `could not select device driver "nvidia" with capabilities: [[gpu]]`，说明 Docker daemon 尚未注册 NVIDIA runtime。先安装/配置 NVIDIA Container Toolkit 并重启 Docker，再重新执行 `docker compose up -d`。

健康检查：

```bash
curl http://127.0.0.1:58000/api/healthz
```

## 本地开发

后端：

```bash
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

用户前台：

```bash
cd frontend/user-app
npm install
npm run dev
```

默认 Vite 地址通常为：

```text
http://127.0.0.1:5173
```

用户前台的 Vite 开发服务器已配置 `/api -> http://127.0.0.1:8000` 代理，管理员后台路由由同一个 `frontend/user-app/` 应用内的 `/admin/` 承载。

## 配置

后端配置使用 `YOLO_PLATFORM_` 环境变量前缀：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `YOLO_PLATFORM_RUNTIME_ROOT` | `runtime` | 运行时目录；Docker 中通过 `./runtime:/app/runtime` 持久化 |
| `YOLO_PLATFORM_DATABASE_URL` | `sqlite:///.../runtime/app.db` | 数据库连接；默认使用 SQLite |
| `YOLO_PLATFORM_ADMIN_SECRET` | `dev-secret` | 管理员登录密钥，线上环境必须覆盖 |
| `YOLO_PLATFORM_ADMIN_TOKEN_SECRET` | 同 `YOLO_PLATFORM_ADMIN_SECRET` | 管理员 token 签名密钥 |
| `YOLO_PLATFORM_ADMIN_TOKEN_TTL_SECONDS` | `3600` | 管理员 token 有效期 |
| `YOLO_PLATFORM_ADMIN_IP_WHITELIST` | 空 | 管理员免密 IP 白名单，支持逗号分隔的 IP 或 CIDR |
| `YOLO_PLATFORM_ADMIN_TRUSTED_PROXY_CIDRS` | `172.16.0.0/12`（Compose） | 允许后端信任 `X-Real-IP` 的直连代理 IP 或 CIDR |

Docker 后端同时设置了 `MODELS_DIR=/data/models` 供旧版推理链路和新平台模型管理使用，并通过 Compose GPU reservation 向后端容器暴露 NVIDIA GPU。管理员模型列表会自动扫描该目录下的 `.onnx` 文件并导入缺失记录，记录中的模型路径使用 `/data/models/<model>.onnx` 形式。

## 管理员后台

管理员后台由 `frontend/user-app/` 内置承载，访问 `/admin/` 后输入管理员密钥登录；命中管理员 IP 白名单的来源可免密进入。

模型发布流程：

1. 将 `.onnx` 模型文件放入宿主机 `models/`。
2. 启动 Docker Compose。
3. 访问 `http://127.0.0.1:58000/admin/`。
4. 进入模型管理页，列表加载或点击“刷新模型目录”会自动导入缺失的 `.onnx` 记录。
5. 也可以在模型管理页直接上传 `.onnx` 文件，后端会保存到 `MODELS_DIR` 并创建模型记录。
6. 发布模型；如需作为人员筛选默认模型，`model_kind` 必须为 `person_detector`。

自动导入和上传只创建未发布模型记录，不会自动启用、不会自动对高级模式可见，也不会自动设为默认人员模型。

系统配置页当前支持调整：

- `task_slots`：任务并发槽位，范围 `1` 到 `3`
- `gpu_slots`：GPU 推理槽位，范围 `1` 到 `3`

任务监控页当前支持查看任务列表、查看单个任务详情与关键日志、通过短期 SSE token 订阅实时事件、下载已完成任务输出、取消任务和重试失败任务。

## API 摘要

公开接口：

- `GET /api/healthz`
- `POST /api/jobs`（支持 `mode`、`model_id`、`payload`，高级模式可传 conf/iou/batch/imgsz/draw_boxes/save_txt 等）
- `POST /api/jobs/{job_code}/upload?access_token=...`
- `GET /api/jobs/{job_code}?access_token=...`（含 `summary` 统计字段）
- `POST /api/jobs/{job_code}/events-token`（使用 `access_token` 签发短期 SSE token）
- `GET /api/jobs/{job_code}/events?events_token=...`（SSE 实时事件流）
- `GET /api/jobs/{job_code}/detections?access_token=...`（逐图检测结果）
- `GET /api/jobs/{job_code}/images/{file_path}?access_token=...`（结果图片，含路径遍历防护）
- `GET /api/jobs/{job_code}/download?access_token=...`
- `GET /api/jobs/models`

管理员接口：

- `POST /api/admin/login`
- `GET /api/admin/models`
- `POST /api/admin/models`
- `POST /api/admin/models/refresh`
- `POST /api/admin/models/upload`
- `PATCH /api/admin/models/{model_id}/publish`
- `GET /api/admin/configs`
- `PUT /api/admin/configs/concurrency`
- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{job_id}`
- `POST /api/admin/jobs/{job_id}/events-token`（签发短期 SSE token）
- `GET /api/admin/jobs/{job_id}/events?sse_token=...`（SSE 实时事件流；IP 白名单来源可免 token）
- `GET /api/admin/jobs/{job_id}/detections`
- `GET /api/admin/jobs/{job_id}/images/{file_path}`
- `GET /api/admin/jobs/{job_id}/download`
- `POST /api/admin/jobs/{job_id}/cancel`
- `POST /api/admin/jobs/{job_id}/retry`

## 测试

后端：

```bash
python -m pytest tests/backend -v
```

用户前台：

```bash
cd frontend/user-app
npm test
```

前端生产构建：

```bash
cd frontend/user-app && npm run build
```

## 兼容与边界

- 默认 Docker 入口已经切换为 FastAPI 后端，不再启动 Gradio。
- `webui/` 仍可用于旧工具链调试，后端推理适配层继续复用 `webui.processing`。
- 当前 Compose 不再启动 MongoDB，也不使用 `fo_data/`。
- Docker Compose 默认向后端容器暴露全部 NVIDIA GPU；如部署环境需要固定 GPU，请在 `backend.deploy.resources.reservations.devices` 中配置 `device_ids`。
- 公开前台的人员筛选模式可上传图片或 `.zip` 压缩包，后端会解压支持的图片、绑定已发布的默认人员模型并入队执行；`.zip` 每次都会重新上传并解压到当前任务目录；高级模式已支持自定义 `model_id` 与 `payload` 参数并上传文件入队。
- SSE 实时事件推送基于进程内内存事件总线，仅适用于单 worker Uvicorn 部署；多 worker 需引入 Redis pub/sub（本次未实现）。公开端和管理员端均先签发短期 SSE token 再订阅事件，前端在 SSE 不可用时自动降级为轮询。
- 任务完成后会落盘 `summary_json` 统计（by_label/耗时/批次/设备等）与逐图检测结果 `_detections.json`，并随结果压缩包打包。

## OpenCodeReview 自动代码审查

本仓库已接入 [OpenCodeReview](https://github.com/alibaba/open-code-review) GitHub Actions 工作流（`.github/workflows/ocr-review.yml`）。PR 打开、推送新提交或重新打开时，会自动运行代码审查并在 PR 上发布中文行内评论与汇总结论。也可以在 PR 评论中发送 `@open-code-review` 或 `/open-code-review` 手动触发重新审查。

### 配置 Secrets

在仓库 **Settings → Secrets and variables → Actions → Repository secrets** 中添加以下配置：

| Secret | 是否必需 | 默认值 | 说明 |
|--------|---------|--------|------|
| `OCR_LLM_URL` | **是** | 无 | LLM API 地址，OpenAI 兼容格式，例如 `https://api.openai.com/v1/chat/completions` |
| `OCR_LLM_AUTH_TOKEN` | **是** | 无 | LLM API 认证 Token |
| `OCR_LLM_MODEL` | 否 | `gpt-4o` | 模型名称 |
| `OCR_LLM_USE_ANTHROPIC` | 否 | 空 / `false` | 使用 Anthropic Claude 模型时设为 `true`，会影响思考强度参数格式 |
| `OCR_LLM_REASONING_EFFORT` | 否 | 空 | 控制 LLM 思考强度。OpenAI 兼容模式可填 `low` / `medium` / `high` / `xhigh`；Anthropic Claude 模式可填数字表示 `budget_tokens`，例如 `16000` |

### 思考强度配置说明

- 未配置 `OCR_LLM_REASONING_EFFORT` 时，默认禁用 thinking 模式。
- 当 `OCR_LLM_USE_ANTHROPIC` 为 `true` 时，`OCR_LLM_REASONING_EFFORT` 会作为 Claude 的 `thinking.budget_tokens` 传入（需为数字）。
- 当 `OCR_LLM_USE_ANTHROPIC` 为空或 `false` 时，`OCR_LLM_REASONING_EFFORT` 会作为 OpenAI 兼容接口的 `reasoning_effort` 传入（可填 `low` / `medium` / `high` / `xhigh`）。

配置示例：

- OpenAI `o3` / `o1` 系列：`OCR_LLM_REASONING_EFFORT=low`
- Anthropic Claude：`OCR_LLM_USE_ANTHROPIC=true`，`OCR_LLM_REASONING_EFFORT=16000`
