# YOLO 公网多用户推理平台

本仓库正在从单机 Gradio 推理工具演进为面向公网匿名用户的多用户 YOLO 推理平台。当前主线由 FastAPI 后端、两个 React 前端和 Nginx 统一入口组成；旧版 `webui/` 仍保留为推理内核与调试入口。

## 当前能力

- `backend/`：FastAPI API 服务，提供公开任务创建、人员筛选上传入队、状态/日志查询、结果下载、管理员登录、模型管理、并发配置、任务监控、详情、取消、重试与下载接口。
- `frontend/user-app/`：匿名用户前台，包含首页、人员筛选入口、高级模式入口和任务进度/关键日志/结果下载视图。
- `frontend/admin-app/`：管理员后台，包含密钥登录、模型管理、系统配置和任务监控页面。
- `gateway/`：Nginx 统一入口，将用户前台、管理员后台和 `/api/` 转发到同一端口。
- `webui/`：旧版 Gradio 工具链与 `webui.processing.run_inference` 推理实现，后端 `TaskRunner` 通过适配层复用它。

当前阶段已经打通人员筛选模式的任务创建、图片/压缩包上传、归档解压、任务入队、状态/关键日志查询和已完成任务结果下载链路。高级模式仍只支持公开模型列表和任务凭证基础能力，模型参数与文件上传提交尚未接入公开 API。

## 目录结构

```text
.
├── backend/                 # FastAPI、数据库模型、服务层、仓储层、worker 基础能力
├── frontend/
│   ├── admin-app/           # 管理员后台，Vite + React
│   └── user-app/            # 匿名用户前台，Vite + React
├── gateway/                 # Docker Compose 统一入口 Nginx 配置
├── images/                  # 旧版 webui 默认图片目录，当前 Compose 不挂载
├── models/                  # 模型文件目录，Docker 中挂载为 /data/models
├── runtime/                 # 运行时工作区，保存 SQLite、上传、任务和结果产物
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

当前 `docker-compose.yml` 会启动 4 个容器：

- `backend`：FastAPI 后端，容器内监听 `8000`
- `user-app`：匿名用户前台静态站点
- `admin-app`：管理员后台静态站点
- `gateway`：统一入口 Nginx，对宿主机暴露 `58000`

访问地址：

```text
http://127.0.0.1:58000/
```

路由分发：

- `/`：用户前台
- `/admin/`：管理员后台
- `/api/...`：后端 API

gateway 默认允许最大 `100g` 请求体，用于人员筛选模式上传图片或压缩包；后端同步按上传原始文件大小限制为 100G，不再按解压后的图片数量或总大小限制。

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

管理员后台：

```bash
cd frontend/admin-app
npm install
npm run dev
```

默认 Vite 地址通常为：

```text
http://127.0.0.1:5174
```

两个前端的 Vite 开发服务器都已配置 `/api -> http://127.0.0.1:8000` 代理。Docker 构建管理员后台时会设置 `VITE_BASE_PATH=/admin/`，用于匹配 gateway 下的 `/admin/` 子路径部署。

## 配置

后端配置使用 `YOLO_PLATFORM_` 环境变量前缀：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `YOLO_PLATFORM_RUNTIME_ROOT` | `runtime` | 运行时目录；Docker 中通过 `./runtime:/app/runtime` 持久化 |
| `YOLO_PLATFORM_DATABASE_URL` | `sqlite:///.../runtime/app.db` | 数据库连接；默认使用 SQLite |
| `YOLO_PLATFORM_ADMIN_SECRET` | `dev-secret` | 管理员登录密钥，生产环境必须覆盖 |
| `YOLO_PLATFORM_ADMIN_TOKEN_SECRET` | 同 `YOLO_PLATFORM_ADMIN_SECRET` | 管理员 token 签名密钥 |
| `YOLO_PLATFORM_ADMIN_TOKEN_TTL_SECONDS` | `3600` | 管理员 token 有效期 |

Docker 后端同时设置了 `MODELS_DIR=/data/models` 供旧版推理链路使用，并通过 Compose GPU reservation 向后端容器暴露 NVIDIA GPU。通过管理员后台创建模型记录时，容器内推荐填写 `/data/models/<model>.onnx` 形式的模型路径。

## 管理员后台

默认开发密钥为：

```text
dev-secret
```

模型发布流程：

1. 将 `.onnx` 模型文件放入宿主机 `models/`。
2. 启动 Docker Compose。
3. 访问 `http://127.0.0.1:58000/admin/`。
4. 使用管理员密钥登录。
5. 在模型管理页创建模型记录，填写容器内模型路径，例如 `/data/models/person.onnx`。
6. 发布模型；如需作为人员筛选默认模型，`model_kind` 必须为 `person_detector`。

系统配置页当前支持调整：

- `task_slots`：任务并发槽位，范围 `1` 到 `3`
- `gpu_slots`：GPU 推理槽位，范围 `1` 到 `3`

任务监控页当前支持查看任务列表、查看单个任务详情与关键日志、下载已完成任务输出、取消任务和重试失败任务。

## API 摘要

公开接口：

- `GET /api/healthz`
- `POST /api/jobs`
- `POST /api/jobs/{job_code}/upload?access_token=...`
- `GET /api/jobs/{job_code}?access_token=...`
- `GET /api/jobs/{job_code}/download?access_token=...`
- `GET /api/jobs/models`

管理员接口：

- `POST /api/admin/login`
- `GET /api/admin/models`
- `POST /api/admin/models`
- `PATCH /api/admin/models/{model_id}/publish`
- `GET /api/admin/configs`
- `PUT /api/admin/configs/concurrency`
- `GET /api/admin/jobs`
- `GET /api/admin/jobs/{job_id}`
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

管理员后台：

```bash
cd frontend/admin-app
npm test
```

前端生产构建：

```bash
cd frontend/user-app && npm run build
cd ../admin-app && npm run build
```

## 兼容与边界

- 默认 Docker 入口已经切换为 FastAPI 后端，不再启动 Gradio。
- `webui/` 仍可用于旧工具链调试，后端推理适配层继续复用 `webui.processing`。
- 当前 Compose 不再启动 MongoDB，也不使用 `fo_data/`。
- Docker Compose 默认向后端容器暴露全部 NVIDIA GPU；如部署环境需要固定 GPU，请在 `backend.deploy.resources.reservations.devices` 中配置 `device_ids`。
- 公开前台的人员筛选模式可上传图片或 `.zip` 压缩包，后端会解压支持的图片、绑定已发布的默认人员模型并入队执行；高级模式的模型参数与文件上传提交仍需后续接入。
