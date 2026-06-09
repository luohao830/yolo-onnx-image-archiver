# 管理员后台与入口切换实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建管理员后台、模型与系统配置管理能力，并完成从 Gradio 主入口到新 API/前端入口的切换。

**架构：** 管理员后台分为后端鉴权和前端控制台两部分。后端通过单密钥登录签发短时管理令牌，前端控制台负责模型发布、并发配置和任务监控；最终 Docker 与 README 改为以 API 服务和新前端为主入口。

**技术栈：** FastAPI、itsdangerous、React、TypeScript、Vite、Vitest、Docker Compose。

---

## 文件结构

- 修改：`requirements.txt`，增加 `itsdangerous`。
- 创建：`backend/core/admin_auth.py`，签发和校验管理员令牌。
- 创建：`backend/api/deps.py`，提供 `require_admin` 鉴权依赖。
- 创建：`backend/api/routes/admin_auth.py`，管理员登录接口。
- 创建：`backend/api/routes/admin_models.py`，模型 CRUD 和发布接口。
- 创建：`backend/api/routes/admin_configs.py`，系统配置接口。
- 创建：`backend/api/routes/admin_jobs.py`，任务列表、取消、重试接口。
- 创建：`backend/services/model_service.py`，模型发布和默认模型切换服务。
- 创建：`backend/services/config_service.py`，系统配置读写服务。
- 修改：`backend/services/job_service.py`，增加管理员任务列表、取消和重试方法。
- 修改：`backend/main.py`，挂载管理员 API。
- 创建：`tests/backend/test_admin_auth_api.py`
- 创建：`tests/backend/test_admin_models_api.py`
- 创建：`tests/backend/test_admin_jobs_api.py`
- 创建：`frontend/admin-app/package.json`
- 创建：`frontend/admin-app/tsconfig.json`
- 创建：`frontend/admin-app/vite.config.ts`
- 创建：`frontend/admin-app/src/main.tsx`
- 创建：`frontend/admin-app/src/App.tsx`
- 创建：`frontend/admin-app/src/api/client.ts`
- 创建：`frontend/admin-app/src/pages/LoginPage.tsx`
- 创建：`frontend/admin-app/src/pages/ModelsPage.tsx`
- 创建：`frontend/admin-app/src/pages/ConfigsPage.tsx`
- 创建：`frontend/admin-app/src/pages/JobsPage.tsx`
- 创建：`frontend/admin-app/src/pages/__tests__/LoginPage.test.tsx`
- 创建：`frontend/admin-app/src/pages/__tests__/ModelsPage.test.tsx`
- 创建：`frontend/admin-app/src/pages/__tests__/JobsPage.test.tsx`
- 修改：`Dockerfile`，改为运行 FastAPI。
- 修改：`docker-compose.yml`，增加 `runtime/` 挂载和 API 端口。
- 修改：`README.md`，切换到新平台运行说明。
- 可选保留：`webui/app.py`，仅作为调试入口，不再作为默认容器入口。

## 任务 1：实现管理员鉴权后端

**文件：**
- 修改：`requirements.txt`
- 创建：`backend/core/admin_auth.py`
- 创建：`backend/api/deps.py`
- 创建：`backend/api/routes/admin_auth.py`
- 测试：`tests/backend/test_admin_auth_api.py`

- [ ] **步骤 1：编写失败的管理员登录测试**

```python
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_admin_login_returns_token_for_valid_secret() -> None:
    response = client.post("/api/admin/login", json={"secret": "dev-secret"})
    assert response.status_code == 200
    assert "token" in response.json()


def test_admin_login_rejects_invalid_secret() -> None:
    response = client.post("/api/admin/login", json={"secret": "bad-secret"})
    assert response.status_code == 401
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_admin_auth_api.py -v`

预期：`/api/admin/login` 返回 404。

- [ ] **步骤 3：实现最小管理员令牌流程**

`requirements.txt` 追加：

```text
itsdangerous
```

`backend/core/admin_auth.py`：

```python
from itsdangerous import URLSafeTimedSerializer


class AdminTokenService:
    def __init__(self, secret_key: str) -> None:
        self.serializer = URLSafeTimedSerializer(secret_key=secret_key, salt="admin-auth")

    def issue(self) -> str:
        return self.serializer.dumps({"role": "admin"})

    def verify(self, token: str) -> dict:
        return self.serializer.loads(token, max_age=3600)
```

`backend/api/routes/admin_auth.py`：

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.admin_auth import build_admin_token_service

router = APIRouter(prefix="/admin", tags=["admin-auth"])


class LoginRequest(BaseModel):
    secret: str


@router.post("/login")
def admin_login(payload: LoginRequest):
    if payload.secret != "dev-secret":
        raise HTTPException(status_code=401, detail="invalid secret")
    token_service = build_admin_token_service("dev-secret")
    return {"token": token_service.issue()}
```

- [ ] **步骤 4：补齐鉴权依赖并验证通过**

运行：`pytest tests/backend/test_admin_auth_api.py -v`

预期：成功登录和失败登录测试都 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add requirements.txt backend/core/admin_auth.py backend/api/routes/admin_auth.py tests/backend/test_admin_auth_api.py
git commit -m "feat: add admin authentication api"
```

## 任务 2：实现模型管理与系统配置 API

**文件：**
- 创建：`backend/services/model_service.py`
- 创建：`backend/services/config_service.py`
- 创建：`backend/api/routes/admin_models.py`
- 创建：`backend/api/routes/admin_configs.py`
- 测试：`tests/backend/test_admin_models_api.py`

- [ ] **步骤 1：编写失败的模型管理测试**

```python
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_admin_can_create_model_record() -> None:
    response = client.post(
        "/api/admin/models",
        headers={"Authorization": "Bearer admin-token"},
        json={"name": "helmet-person-v1", "slug": "helmet-person-v1", "model_kind": "person_detector"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "helmet-person-v1"
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_admin_models_api.py -v`

预期：`/api/admin/models` 不存在，或未鉴权。

- [ ] **步骤 3：实现模型和配置接口**

`backend/api/routes/admin_models.py`：

```python
from fastapi import APIRouter, Depends, status

from backend.api.deps import require_admin
from backend.services.config_service import config_service
from backend.services.model_service import model_service

router = APIRouter(prefix="/admin/models", tags=["admin-models"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_model(payload: CreateModelRequest, admin=Depends(require_admin)):
    record = model_service.create_model(payload)
    return ModelResponse.model_validate(record)


@router.patch("/{model_id}/publish")
def publish_model(model_id: int, payload: PublishModelRequest, admin=Depends(require_admin)):
    return ModelResponse.model_validate(model_service.publish_model(model_id, payload))
```

`backend/api/routes/admin_configs.py`：

```python
from fastapi import APIRouter, Depends


router = APIRouter(prefix="/admin/configs", tags=["admin-configs"])


@router.get("")
def list_configs(admin=Depends(require_admin)):
    return config_service.list_configs()


@router.put("/concurrency")
def update_concurrency(payload: UpdateConcurrencyRequest, admin=Depends(require_admin)):
    return config_service.update_concurrency(payload.task_slots, payload.gpu_slots)
```

- [ ] **步骤 4：补齐默认人检模型和 GPU 并发配置测试后验证通过**

运行：`pytest tests/backend/test_admin_models_api.py -v`

预期：模型创建、发布、默认模型切换、并发配置更新 4 类测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/api/routes/admin_models.py backend/api/routes/admin_configs.py tests/backend/test_admin_models_api.py
git commit -m "feat: add admin model and config apis"
```

## 任务 3：实现管理员任务监控与运维 API

**文件：**
- 修改：`backend/services/job_service.py`
- 创建：`backend/api/routes/admin_jobs.py`
- 测试：`tests/backend/test_admin_jobs_api.py`

- [ ] **步骤 1：编写失败的任务管理测试**

```python
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_admin_can_cancel_queued_job() -> None:
    response = client.post("/api/admin/jobs/12/cancel", headers={"Authorization": "Bearer admin-token"})
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`pytest tests/backend/test_admin_jobs_api.py -v`

预期：管理任务路由不存在。

- [ ] **步骤 3：实现任务列表、取消和重试接口**

```python
from fastapi import APIRouter, Depends

from backend.api.deps import require_admin
from backend.services.job_service import job_service

router = APIRouter(prefix="/admin/jobs", tags=["admin-jobs"])


@router.get("")
def list_jobs(admin=Depends(require_admin)):
    return job_service.list_admin_jobs()


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, admin=Depends(require_admin)):
    return job_service.cancel_job(job_id)


@router.post("/{job_id}/retry")
def retry_job(job_id: int, admin=Depends(require_admin)):
    return job_service.retry_job(job_id)
```

- [ ] **步骤 4：验证排队任务取消、失败任务重试、运行中任务只打取消标记**

运行：`pytest tests/backend/test_admin_jobs_api.py -v`

预期：3 类状态流测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add backend/api/routes/admin_jobs.py tests/backend/test_admin_jobs_api.py
git commit -m "feat: add admin job operations api"
```

## 任务 4：搭建管理员前端与登录页

**文件：**
- 创建：`frontend/admin-app/package.json`
- 创建：`frontend/admin-app/tsconfig.json`
- 创建：`frontend/admin-app/vite.config.ts`
- 创建：`frontend/admin-app/src/main.tsx`
- 创建：`frontend/admin-app/src/App.tsx`
- 创建：`frontend/admin-app/src/api/client.ts`
- 创建：`frontend/admin-app/src/pages/LoginPage.tsx`
- 测试：`frontend/admin-app/src/pages/__tests__/LoginPage.test.tsx`

- [ ] **步骤 1：编写失败的后台登录页测试**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LoginPage } from "../LoginPage";


it("stores admin token after successful login", async () => {
  render(<LoginPage />);

  fireEvent.change(screen.getByLabelText("管理员密钥"), { target: { value: "dev-secret" } });
  fireEvent.click(screen.getByRole("button", { name: "进入后台" }));

  await waitFor(() => {
    expect(screen.getByText("模型管理")).toBeInTheDocument();
  });
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/admin-app && npm test -- LoginPage.test.tsx`

预期：后台前端目录不存在。

- [ ] **步骤 3：创建管理员前端骨架和登录页**

`frontend/admin-app/src/pages/LoginPage.tsx`：

```tsx
import { useState } from "react";

import { adminLogin } from "../api/client";


export function LoginPage() {
  const [secret, setSecret] = useState("");
  const [token, setToken] = useState("");

  async function handleSubmit() {
    const result = await adminLogin(secret);
    setToken(result.token);
    localStorage.setItem("admin-token", result.token);
  }

  return (
    <section>
      <label htmlFor="admin-secret">管理员密钥</label>
      <input id="admin-secret" value={secret} onChange={(event) => setSecret(event.target.value)} />
      <button onClick={handleSubmit}>进入后台</button>
      {token ? <div>模型管理</div> : null}
    </section>
  );
}
```

- [ ] **步骤 4：验证登录成功和登录失败提示**

运行：`cd frontend/admin-app && npm test -- LoginPage.test.tsx`

预期：成功登录与失败提示测试都 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add frontend/admin-app
git commit -m "feat: scaffold admin console"
```

## 任务 5：实现模型页、配置页和任务页

**文件：**
- 创建：`frontend/admin-app/src/pages/ModelsPage.tsx`
- 创建：`frontend/admin-app/src/pages/ConfigsPage.tsx`
- 创建：`frontend/admin-app/src/pages/JobsPage.tsx`
- 测试：`frontend/admin-app/src/pages/__tests__/ModelsPage.test.tsx`
- 测试：`frontend/admin-app/src/pages/__tests__/JobsPage.test.tsx`

- [ ] **步骤 1：编写失败的模型页测试**

```tsx
import { render, screen, waitFor } from "@testing-library/react";

import { ModelsPage } from "../ModelsPage";


it("lists published models and default person model badge", async () => {
  render(<ModelsPage />);

  await waitFor(() => {
    expect(screen.getByText("helmet-person-v1")).toBeInTheDocument();
    expect(screen.getByText("默认人检模型")).toBeInTheDocument();
  });
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/admin-app && npm test -- ModelsPage.test.tsx`

预期：页面和接口尚不存在。

- [ ] **步骤 3：实现三页基础能力**

`frontend/admin-app/src/pages/ModelsPage.tsx`：

```tsx
export function ModelsPage() {
  return (
    <section>
      <h2>模型管理</h2>
      <button>上传 ONNX</button>
      <button>设为默认人检模型</button>
    </section>
  );
}
```

`frontend/admin-app/src/pages/ConfigsPage.tsx`：

```tsx
export function ConfigsPage() {
  return (
    <section>
      <h2>系统配置</h2>
      <label>任务处理器并发数</label>
      <label>GPU 推理并发数</label>
    </section>
  );
}
```

`frontend/admin-app/src/pages/JobsPage.tsx`：

```tsx
export function JobsPage() {
  return (
    <section>
      <h2>任务监控</h2>
      <button>取消任务</button>
      <button>重试任务</button>
    </section>
  );
}
```

- [ ] **步骤 4：补齐上传 sidecar、默认模型切换、取消/重试动作并验证通过**

运行：`cd frontend/admin-app && npm test -- ModelsPage.test.tsx JobsPage.test.tsx`

预期：模型页、配置页、任务页测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add frontend/admin-app/src/pages frontend/admin-app/src/pages/__tests__
git commit -m "feat: add admin models configs and jobs pages"
```

## 任务 6：切换 Docker 和文档主入口

**文件：**
- 修改：`Dockerfile`
- 修改：`docker-compose.yml`
- 修改：`README.md`

- [ ] **步骤 1：将容器入口改为 FastAPI**

`Dockerfile` 入口改为：

```dockerfile
ENTRYPOINT ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **步骤 2：调整 Compose 暴露端口与运行目录**

`docker-compose.yml` 至少保留：

```yaml
ports:
  - "58000:8000"
volumes:
  - ./models:/data/models
  - ./runtime:/data/runtime
```

- [ ] **步骤 3：重写 README 入口说明**

README 至少覆盖：

```markdown
## 用户前台
## 管理员后台
## API 服务
## runtime 目录
## 模型发布流程
```

- [ ] **步骤 4：运行整体验证**

运行：

```bash
pytest tests/backend -v
cd frontend/user-app && npm test && npm run build
cd ../admin-app && npm test && npm run build
docker compose config
```

预期：后端测试通过、两套前端测试和构建通过、Compose 配置合法。

- [ ] **步骤 5：Commit**

```bash
git add Dockerfile docker-compose.yml README.md
git commit -m "chore: switch product entrypoint to api platform"
```
