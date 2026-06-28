# 仓库指南（请注意：此仓库的后续回复一律使用中文）

## 项目定位

YOLO 多用户推理平台，让用户无需账户即可提交图片/压缩包进行 YOLO 推理，并在任务全生命周期中获得状态、日志和结果下载。仓库包含 FastAPI 后端、内置管理员后台的 React 前台、Nginx 统一入口，以及旧版 Gradio 工具链 `webui/`（当前仅作为推理内核被后端适配层复用）。

## 协作与实现原则

- 禁止自作主张做“最小化实现”而忽略用户设计要求；必须按用户确认的目标架构最大努力完成。
- 禁止过度保守；用户提出提高效率、多个 worktree 并行推进时，必须给出可行、清晰的并行方案。
- 禁止未讨论充分就直接改代码；架构和模块设计未确认前，只做文档讨论和设计沉淀。

## 常用命令

### Docker Compose 启动（生产/集成验证）

```bash
mkdir -p models runtime
docker compose build
docker compose up -d
```

访问：`http://127.0.0.1:58000/`  
路由：`/` 用户前台，`/admin/` 管理员后台，`/api/...` 后端 API。

常用运维：

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f gateway
docker compose down
```

### 后端本地开发

```bash
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

后端入口 `backend/main.py`，所有路由前缀 `/api`。

### 前端本地开发

```bash
cd frontend/user-app
npm install
npm run dev
```

Vite 开发服务器默认 `http://127.0.0.1:5173`，并将 `/api` 代理到 `http://127.0.0.1:8000`。管理员后台由同一个 `frontend/user-app/` 应用承载，访问 `/admin/`。

### 测试

后端全部测试：

```bash
python -m pytest tests/backend -v
```

运行单个测试文件或单个用例：

```bash
python -m pytest tests/backend/test_archive_ingest.py -v
python -m pytest tests/backend/test_scheduler.py::test_scheduler_runs_pending_jobs -v
```

前端测试：

```bash
cd frontend/user-app
npm test
```

前端构建验证：

```bash
cd frontend/user-app && npm run build
```

### 健康检查

```bash
curl http://127.0.0.1:58000/api/healthz
```

## 项目结构与路径

- 根目录包含容器编排与后端镜像文件：`docker-compose.yml`、`Dockerfile`、`requirements.txt`。
- `backend/` 是 FastAPI 后端，包含 API 路由、服务层、仓储层、数据库模型、运行时路径管理和 worker 基础能力。
- `frontend/user-app/` 是用户前台与内置管理员后台，使用 Vite + React + TypeScript。
- `gateway/` 保存统一入口 Nginx 配置；Docker Compose 通过 `gateway` 将 `/` 和 `/api/` 聚合到宿主机 `58000` 端口，`/admin/` 由 `user-app` 的前端路由承载；访问日志使用不含 query string 的格式，避免任务凭证和短期 SSE token 落盘。
- `webui/` 是旧版 Gradio 工具链和推理内核，当前不再是默认容器入口，但 `backend/services/inference_adapter.py` 会复用 `webui.processing`。
- `models/` 保存宿主机模型文件，Docker 后端挂载为 `/data/models`。
- `runtime/` 是运行时工作区，保存 SQLite 数据库、上传文件、任务目录、结果目录和临时文件；不要提交运行产物。
- `images/` 主要服务旧版 `webui/` 工作流，当前 Docker Compose 不挂载该目录。
- `tests/backend/` 保存后端单元测试与 API smoke 测试；前端测试放在各自 `src/**/__tests__/` 附近。

## 当前架构状态

- 主线平台由 `backend`、`user-app` 和 `gateway` 3 个 Compose 服务组成。
- 后端默认使用 SQLite，数据库文件位于 `runtime/app.db`；当前没有 MongoDB，也不使用 `fo_data/`。
- 公开接口已支持创建任务凭证、人员筛选与高级模式上传入队、查询任务状态/关键日志、短期 token 鉴权的 SSE 实时事件推送、下载已完成任务结果压缩包、获取逐图检测结果与结果图片、列出高级模式可见模型。
- 管理员接口面向内网单机访问，已支持模型创建/目录刷新/ONNX 上传/发布、并发配置、任务列表、任务详情、结果下载、取消、重试、短期 token 鉴权的 SSE 实时事件、逐图检测结果与结果图片。
- 公开前台的人员筛选模式已接入图片或 `.zip` 压缩包上传、归档解压、默认人员模型绑定和任务入队；高级模式已接通 `model_id` 与 `payload`（conf/iou/batch/imgsz/draw_boxes/save_txt 等，服务端 normalize 合并默认值）创建任务并上传文件入队。

## 后端分层

- `backend/api/routes/`：路由实现；公开接口在 `public_jobs.py`，管理员接口在 `admin_*.py`。
- `backend/api/deps.py`：依赖注入，管理员鉴权通过 `require_admin` 实现。
- `backend/services/`：业务逻辑。`job_service.py` 负责任务创建、上传、序列化；`scheduler_service.py` 组装调度器；`inference_adapter.py` 对接 `webui.processing`；`archive_ingest.py` 处理 `.zip` 解压；`runtime_paths.py` 管理运行时目录。
- `backend/repositories/`：SQLAlchemy 数据访问，目录下有 `jobs.py`、`models.py`、`system_configs.py`。
- `backend/db/models.py`：全部数据库模型（`JobRecord`、`ModelRecord`、`SystemConfigRecord`、`JobEventRecord`）。
- `backend/core/`：配置（`config.py`，环境变量前缀 `YOLO_PLATFORM_`）、数据库连接（`db.py`）、管理员鉴权（`admin_auth.py`）。
- `backend/workers/`：`Scheduler` 负责任务队列与线程池；`GpuGate` 限制并发 GPU 推理槽位；`TaskRunner` 调用推理适配层并写入进度事件。

## 调度与推理流程

1. `POST /api/jobs` 创建任务，返回 `job_code` 和 `access_token`。
2. `POST /api/jobs/{job_code}/upload` 接收图片或 `.zip`，校验、解压、绑定默认人员模型，然后 `scheduler.submit(job_id)`。
3. `Scheduler` 使用固定线程池消费队列，每个线程通过 `DatabaseTaskRunner` 新建独立会话运行 `TaskRunner.run(job_id)`。
4. `TaskRunner` 获取任务、模型与 `payload_json`，经 `GpuGate` 调用 `inference_adapter.run_job_inference`，后者委托 `webui.processing.run_inference`。
5. 推理回调 `ProgressEventWriter` 将进度写入 `JobEventRecord`（节流到每 2 秒或处理数变化）。
6. 完成后调用 `inference_adapter.package_job_output` 生成结果压缩包，更新任务为 `completed`。

## 任务状态

`created` → `uploaded` → `running` → `completed`/`failed`/`canceled`。`cancel_requested` 标记用于运行中任务的取消信号（当前由推理循环自行检查）。

## 管理员鉴权

- `POST /api/admin/login` 用管理员密钥换取 token，默认密钥为 `dev-secret`，仅本地使用。
- 管理员任务 SSE 先通过 `POST /api/admin/jobs/{job_id}/events-token` 签发短期、绑定任务的 `sse_token`，再访问 `GET /api/admin/jobs/{job_id}/events?sse_token=...`；IP 白名单来源保持免 token 兼容。
- `YOLO_PLATFORM_ADMIN_IP_WHITELIST` 可配置免密 IP/CIDR。
- 反代场景下后端仅在直连来源命中 `YOLO_PLATFORM_ADMIN_TRUSTED_PROXY_CIDRS` 时读取 `X-Real-IP`，不信任 `X-Forwarded-For`。

## 配置与运行时约束

- 后端配置使用 `YOLO_PLATFORM_` 环境变量前缀，核心变量包括 `YOLO_PLATFORM_RUNTIME_ROOT`、`YOLO_PLATFORM_DATABASE_URL`、`YOLO_PLATFORM_ADMIN_SECRET`、`YOLO_PLATFORM_ADMIN_TOKEN_SECRET`、`YOLO_PLATFORM_ADMIN_TOKEN_TTL_SECONDS`、`YOLO_PLATFORM_ADMIN_IP_WHITELIST` 和 `YOLO_PLATFORM_ADMIN_TRUSTED_PROXY_CIDRS`。
- 管理员默认密钥为 `dev-secret`，仅可用于本地开发；线上环境必须覆盖。
- Docker 后端将宿主机 `models/` 挂载为 `/data/models`；管理员后台会扫描该目录下的 `.onnx` 并导入缺失记录，也可上传 `.onnx` 到该目录，导入记录默认不自动发布或设为默认人员模型。
- Gateway Nginx 通过 `client_max_body_size 100g` 允许人员筛选模式上传图片或压缩包；后端同步按上传原始文件大小限制为 100G，不再按解压后的图片数量或总大小限制。`.zip` 压缩包每次都会重新上传并解压到当前任务目录，不做 hash 复用或服务端压缩包缓存；gateway 访问日志不得记录 query string，避免 `access_token` 或短期 SSE token 落盘；修改体积、上传语义或日志格式时必须同步文档。
- 管理员 IP 白名单使用 `YOLO_PLATFORM_ADMIN_IP_WHITELIST` 配置，支持逗号分隔 IP 或 CIDR；反代部署时后端仅在直连来源命中 `YOLO_PLATFORM_ADMIN_TRUSTED_PROXY_CIDRS` 时读取 gateway 覆盖写入的 `X-Real-IP`，不信任客户端传入的 `X-Forwarded-For`。
- Docker Compose 默认向后端容器暴露全部 NVIDIA GPU；如需固定 GPU，在 `backend.deploy.resources.reservations.devices` 中使用 `device_ids`，并且不要同时设置 `count`。
- 修改端口、路由、挂载路径、环境变量或模型路径语义时，必须同步更新 `README.md`、`AGENTS.md` 和 PR 描述。

## 模型管理

- 模型记录指向 `.onnx` 文件；Docker 中宿主机 `models/` 挂载为 `/data/models`。
- `GET /api/admin/models` 会自动扫描目录并导入缺失的 `.onnx` 记录。
- 上传/导入的模型默认未发布、未对高级模式可见、未设为默认人员模型，需要管理员在模型管理页发布。
- 只有 `model_kind == person_detector` 的模型可被设为默认人员模型。

## 公开 API 边界

当前公开 API 已实现：任务创建（含高级模式 `model_id`/`payload`）、人员筛选与高级模式上传入队、状态查询、短期 token 鉴权的 SSE 实时事件推送、结果下载、逐图检测结果获取、结果图片获取、列出已发布的高级模式模型。高级模式的任务参数与文件上传提交已接通公开 API。

## 上传与体积限制

- Gateway 设置 `client_max_body_size 100g`；后端按原始文件大小限制 `100G`。
- 不再按解压后的图片数量或总大小限制。
- `.zip` 每次都会重新上传到当前任务目录并解压，不做 hash 复用或服务端压缩包缓存。

## 编码风格与命名

- Python 遵循 PEP 8：4 空格缩进，函数与文件使用 `snake_case`，类使用 `CapWords`。
- FastAPI 路由保持在 `backend/api/routes/`，依赖注入放在 `backend/api/deps.py`，业务逻辑优先放入 `backend/services/`，数据库访问放入 `backend/repositories/`。
- 数据库模型集中在 `backend/db/models.py`；新增持久化字段时同步补充仓储、服务和测试。
- React 组件与页面使用 TypeScript，页面放在 `src/pages/`，通用组件放在 `src/components/`，API 封装放在 `src/api/client.ts` 与 `src/admin-api/client.ts`。
- 公共辅助函数添加简短 docstring 或清晰类型签名；日志优先于 `print`。
- 避免把新平台逻辑继续塞入旧版 `webui/app.py`；除非是在维护旧 Gradio 调试入口或推理内核。

## 设计系统要点（来自 DESIGN.md）

- 品牌气质：冷静、工程化、可信。
- 页面背景 `#f8fafc`，卡片背景 `#ffffff`；主色 `#2563eb` 仅用于主按钮、运行状态、当前进度和焦点环，保持稀缺。
- 深色背景 `#020617` 只用于日志面板。
- 字体使用 Inter 单一家族，等宽字体仅用于日志时间戳和事件类型。
- 状态指示必须同时使用颜色 + 文字/百分比，不单独依赖颜色。
- 遵循 `prefers-reduced-motion: reduce`。

## 测试指南

- 后端测试：`python -m pytest tests/backend -v`。
- 用户前台测试：在 `frontend/user-app/` 下运行 `npm test`。
- 管理员后台测试随 `frontend/user-app/` 一起运行。
- 前端构建验证：在 `frontend/user-app/` 下运行 `npm run build`。
- 修改 API 契约时，补充或更新 `tests/backend/test_*_api.py` 与前端 `src/api/client.ts` 附近的调用测试。
- 修改任务调度、归档解压或推理执行时，优先覆盖 `test_archive_ingest.py`、`test_scheduler.py`、`test_task_runner.py`。
- 未执行的测试必须在回复、提交说明或 PR 描述中明确标注“未执行”并说明原因，不得编造结果。

## 提交与 PR 工作规范

### 1. 工作区要求

* 优先在独立 worktree 中完成开发、验证、提交与推送，避免污染主工作区。
* 开始前检查当前目录是否为独立 worktree，并确认当前分支、目标分支与远端状态。
* 目标分支默认为 `master`，除非用户另有说明。

建议检查项：

```bash
git branch --show-current
git status --short
git worktree list
git remote -v
```

---

### 2. 提交信息生成要求

* 提交信息必须使用 **`superpowers:chinese-commit-conventions`** skill 生成。
* 提交信息必须基于**当前分支的实际改动**，不得根据猜测、计划或未提交内容编写。
* 提交信息必须符合**中文 Conventional Commits** 规范。
* 提交信息不要包含 `Co-Authored-By: Claude <noreply@anthropic.com>` 及任何机器/AI 协作者署名。
* 提交信息必须使用真实的多行格式，确保：

  * 标题、正文、技术方案、影响范围分层清晰
  * 段落之间保留空行
  * 列表项统一使用 `-`
  * 范围、术语、动词保持一致且准确
  * 不夸大影响范围，不遗漏关键改动

提交信息格式示例：

```text
fix(调度器): 避免活跃任务被兜底超时误标记

processing 任务兜底超时统一改用 runtime.workers.timeout，并在任务仍由当前 active worker 持有时跳过终态转换，避免运行中的 worker 任务被误判为超时。

技术方案：
- 移除 `database.task_timeout_minutes` 独立配置与数据库超时重置入口
- 统一 worker 进程超时和 processing 任务兜底超时的秒级配置
- 补充 active worker 持有任务时跳过超时标记的单元测试

影响范围：
- 任务调度器
- 配置管理
- 配置页面
- 单元测试
```

---

### 3. 提交前检查

提交前必须确认以下事项：

* 代码变更已完成且与需求一致
* 已查看实际 diff，确认无无关改动
* 已执行必要测试，并记录命令与结果
* 提交信息已按规范生成
* 涉及 UI、交互、运行日志或报错修复时，已准备截图或日志片段
* 涉及端口、路由、路径、配置或环境变量变更时，已记录变更说明

建议检查项：

```bash
git diff
git status --short
```

---

### 4. PR 描述要求

PR 描述必须包含以下内容：

```md
## 改动范围
- 说明本次 PR 涉及的模块、页面、接口、配置或脚本
- 说明核心行为变化

## 测试
- `python -m pytest tests/backend -v`：通过 / 失败，失败原因为 ...
- `npm test`（frontend/user-app）：通过 / 失败，失败原因为 ...

## 端口 / 路径变更
- 无
```

如有变更，需明确列出：

```md
## 端口 / 路径变更
- 新增路由：`/api/tasks/:id/retry`
- 修改配置：`YOLO_PLATFORM_RUNTIME_ROOT`
- 修改挂载：`./runtime:/app/runtime`
```

截图或日志要求：

```md
## 截图 / 日志
- 无 UI 变更
```

如涉及 UI、交互、报错修复或运行日志，需补充对应截图或关键日志片段。

关联 Issue 要求：

```md
## 关联 Issue
- Closes #123
```

没有关联 Issue 时填写：

```md
## 关联 Issue
- 无
```

---

### 5. 推送与 PR 创建流程

完成开发、测试与提交后：

1. 将本地提交推送到远端当前分支。
2. 向用户汇报以下内容，并提醒用户二次确认：

   * 当前分支
   * 提交摘要
   * 已执行测试命令与结果
   * 远端分支
   * 是否准备基于 `master` 创建 PR
3. 用户确认后，基于目标分支 `master` 创建 PR。
4. 创建 PR 后，提供 PR 链接与摘要。

---

### 6. PR 审查评论处理

PR 创建后，需要轮询等待 PR 审查评论。

收到审查评论后：

1. 阅读并分类评论：

   * 必须修复
   * 建议优化
   * 需要解释
   * 与本次 PR 无关
2. 对需要修改的内容进行实现。
3. 执行必要测试。
4. 使用 **`superpowers:chinese-commit-conventions`** 根据本次审查修复的实际 diff 生成提交信息。
5. 提交并推送到同一 PR 分支。
6. 回复用户本轮处理结果，包括：

   * 已处理的评论
   * 未处理的评论及原因
   * 新增提交
   * 测试结果

如审查评论不明确，不直接猜测实现，应说明不确定点并给出建议处理方案。

---

### 7. 信息真实性要求

* 不得编造测试结果。
* 不得编造截图、日志、Issue 编号或 PR 链接。
* 未执行的测试必须明确标注“未执行”，并说明原因。
* 没有端口、路径、环境变量或路由变更时，明确写“无”。
* 没有关联 Issue 时，明确写“无”。
* PR 描述、提交信息、审查回复必须与实际代码改动一致。

## 相关文档

- `README.md`：更详细的使用说明、API 摘要、兼容与边界。
- `DESIGN.md`：完整设计系统、颜色、排版、组件规范。
- `PRODUCT.md`：产品定位、用户、设计原则、无障碍目标。
