# YOLO 公网多用户推理平台

当前仓库正在从单机 Gradio 工具重构为一个面向公网匿名用户的多用户推理平台。现阶段已经具备以下三块基础能力：

- `backend/`：FastAPI 后端，提供公开任务接口和管理员接口
- `frontend/user-app/`：匿名用户前台
- `frontend/admin-app/`：管理员后台

旧的 `webui/` 仍然保留，作为推理内核和调试入口，不再是默认容器入口。

## 用户前台

用户前台位于 `frontend/user-app/`，当前已接通的页面包括：

- 首页
- 人员筛选模式入口
- 高级模式入口
- 任务凭证查询页
- 任务结果轮询页

本地开发：

```bash
cd frontend/user-app
npm install
npm run dev
```

默认开发地址：

```text
http://127.0.0.1:5173
```

Vite 已配置 `/api -> http://127.0.0.1:8000` 代理。

## 管理员后台

管理员后台位于 `frontend/admin-app/`，当前已接通的页面包括：

- 管理员密钥登录页
- 模型管理页
- 系统配置页
- 任务监控页

本地开发：

```bash
cd frontend/admin-app
npm install
npm run dev
```

默认开发地址：

```text
http://127.0.0.1:5174
```

同样可通过 Vite 代理访问本地后端 API。

## API 服务

默认容器入口已经切换为 FastAPI：

```bash
docker compose build
docker compose up -d
```

默认 API 地址：

```text
http://127.0.0.1:58000
```

关键接口：

- `GET /api/healthz`
- `POST /api/jobs`
- `GET /api/jobs/{job_code}?access_token=...`
- `POST /api/admin/login`
- `GET /api/admin/models`
- `GET /api/admin/configs`
- `GET /api/admin/jobs`

本地后端开发：

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
python -m pytest tests/backend -v
```

## runtime 目录

运行时目录统一收口到 `runtime/`，主要用于：

- 上传包暂存
- 任务工作目录
- 推理结果目录
- 临时文件目录
- SQLite 数据库文件 `runtime/app.db`

建议将 `runtime/` 视为持久化工作区，不要直接提交其中的运行产物。

## 模型发布流程

当前推荐流程如下：

1. 将 `.onnx` 模型及可选 sidecar 文件放入 `models/`
2. 启动后端服务
3. 通过管理员后台登录
4. 在模型管理页创建模型记录并发布
5. 将某个 `person_detector` 模型设为默认人检模型

当前版本已经打通模型记录、发布状态、默认人检模型和高级模式可见性的管理接口；模型文件上传本身仍以本地目录投放为主，后续再接入后台上传。

## 目录概览

```text
.
├── backend/
├── frontend/
│   ├── admin-app/
│   └── user-app/
├── models/
├── runtime/
└── webui/
```

## 兼容说明

- `webui/` 仍可作为旧工具链和推理调试入口
- 默认 Docker 入口已不再启动 Gradio
- 管理员与匿名用户前端目前以独立开发站点运行，尚未做容器内静态托管整合
