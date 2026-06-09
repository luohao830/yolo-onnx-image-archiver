# 任务进度与结果下载改版实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将前台改为提交后展示任务进度、关键日志和结果下载；将后台任务监控改为支持详情查看和输出下载。

**架构：** 后端扩展任务序列化，统一计算进度、公开事件日志和下载可用性；新增公开下载与管理员详情/下载路由。前端用户侧用同页状态面板替代回执/查询流程，管理员侧用任务列表加详情面板替代简单列表。

**技术栈：** FastAPI、SQLAlchemy、pytest、React 18、TypeScript、React Router、Vitest、Testing Library、原生 CSS。

---

## 文件结构

- 修改 `backend/repositories/jobs.py`：增加按任务列出事件的方法。
- 修改 `backend/services/job_service.py`：增加任务详情序列化、进度计算、下载路径解析和安全事件输出。
- 修改 `backend/schemas/jobs.py`：扩展公开状态 schema，增加事件、管理员详情和下载状态字段。
- 修改 `backend/api/routes/public_jobs.py`：新增公开结果下载路由。
- 修改 `backend/api/routes/admin_jobs.py`：新增管理员任务详情和下载路由。
- 修改 `tests/backend/test_public_jobs_api.py`：覆盖公开日志、进度和下载。
- 修改 `tests/backend/test_admin_jobs_api.py`：覆盖管理员详情和下载。
- 创建/修改 `frontend/user-app/src/styles.css` 与 `frontend/admin-app/src/styles.css`：统一控制台视觉系统。
- 修改 `frontend/user-app/src/api/client.ts`：扩展任务状态类型和下载 URL 构造。
- 修改 `frontend/user-app/src/App.tsx`、`HomePage.tsx`、`PersonFilterPage.tsx`、`AdvancedModePage.tsx`、`ResultPage.tsx`：移除查询主流程，加入进度、日志和下载体验。
- 修改用户前台组件测试：验证无可见凭证、进度日志和下载按钮。
- 修改 `frontend/admin-app/src/api/client.ts`：增加任务详情与下载 URL。
- 修改 `frontend/admin-app/src/pages/JobsPage.tsx`：列表 + 详情面板 + 下载。
- 修改管理员前台组件测试：验证详情、日志和下载入口。

## 任务 1：后端任务进度、日志和下载契约

**文件：**
- 修改：`backend/repositories/jobs.py`
- 修改：`backend/services/job_service.py`
- 修改：`backend/schemas/jobs.py`
- 修改：`backend/api/routes/public_jobs.py`
- 修改：`backend/api/routes/admin_jobs.py`
- 测试：`tests/backend/test_public_jobs_api.py`
- 测试：`tests/backend/test_admin_jobs_api.py`

- [ ] **步骤 1：编写失败的后端测试**

在 `tests/backend/test_public_jobs_api.py` 增加测试：

```python
def test_get_public_job_returns_progress_events_and_download_state(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)
    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code(receipt.job_code)
        assert saved is not None
        repo.mark_running(saved.id)
        repo.record_event(saved.id, event_type="running", message="任务开始执行", payload_json={"total": 10, "written": 4, "path": "/secret"})

    payload = get_job(receipt.job_code, receipt.access_token, service=service)

    assert payload.progress == 40
    assert payload.download_ready is False
    assert payload.events[0].message == "任务开始执行"
    assert payload.events[0].payload_json == {"total": 10, "written": 4}
```

在 `tests/backend/test_public_jobs_api.py` 增加下载测试：

```python
def test_download_public_job_result_requires_completed_job_and_token(tmp_path: Path) -> None:
    result_zip = tmp_path / "result.zip"
    result_zip.write_bytes(b"zip-bytes")
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    receipt = create_job(CreateJobRequest(mode="person_filter"), service=service)
    with session_scope(engine) as session:
        repo = JobRepository(session)
        saved = repo.get_by_code(receipt.job_code)
        assert saved is not None
        repo.mark_completed(saved.id, result_dir=str(tmp_path), result_zip_path=str(result_zip))

    response = download_job_result(receipt.job_code, receipt.access_token, service=service)

    assert response.path == str(result_zip)
```

在 `tests/backend/test_admin_jobs_api.py` 增加测试：

```python
def test_admin_can_get_job_detail_with_events_and_download_state(tmp_path: Path) -> None:
    result_zip = tmp_path / "result.zip"
    result_zip.write_bytes(b"zip-bytes")
    engine = build_engine(f"sqlite:///{tmp_path / 'app.db'}")
    create_all(engine)
    service = JobService(engine)
    with session_scope(engine) as session:
        repo = JobRepository(session)
        job = repo.create_job(job_code="JOB-DONE", access_token_hash="hash", mode="advanced")
        repo.record_event(job.id, event_type="completed", message="输出结果压缩包已生成", payload_json={"total": 2, "written": 2})
        repo.mark_completed(job.id, result_dir=str(tmp_path), result_zip_path=str(result_zip))
        job_id = job.id

    detail = get_job_detail(job_id, admin=ADMIN_CLAIMS, service=service)

    assert detail.job_code == "JOB-DONE"
    assert detail.progress == 100
    assert detail.download_ready is True
    assert detail.events[0].message == "输出结果压缩包已生成"
```

- [ ] **步骤 2：运行后端测试验证失败**

运行：`python -m pytest tests/backend/test_public_jobs_api.py tests/backend/test_admin_jobs_api.py -v`

预期：FAIL，原因是 `progress`、`events`、`download_ready`、`download_job_result` 或 `get_job_detail` 尚未实现。

- [ ] **步骤 3：实现后端契约**

实现内容：

- `JobRepository.list_events(job_id)` 按 `JobEventRecord.id.asc()` 返回事件。
- `JobService.get_public_job()` 返回进度、过滤后的事件、`download_ready`。
- `JobService.get_admin_job(job_id)` 返回管理员详情。
- `JobService.resolve_public_result_zip(job_code, access_token)` 校验凭据、completed 状态和 zip 存在。
- `JobService.resolve_admin_result_zip(job_id)` 校验 completed 状态和 zip 存在。
- 路由层用 `FileResponse` 返回 zip。
- `payload_json` 只公开 `total`、`written`、`processed`、`matched`、`skipped`、`error` 等安全摘要字段。

- [ ] **步骤 4：运行后端测试验证通过**

运行：`python -m pytest tests/backend/test_public_jobs_api.py tests/backend/test_admin_jobs_api.py -v`

预期：PASS。

## 任务 2：用户前台任务进度体验

**文件：**
- 修改：`frontend/user-app/src/api/client.ts`
- 修改：`frontend/user-app/src/App.tsx`
- 修改：`frontend/user-app/src/pages/HomePage.tsx`
- 修改：`frontend/user-app/src/pages/PersonFilterPage.tsx`
- 修改：`frontend/user-app/src/pages/AdvancedModePage.tsx`
- 修改：`frontend/user-app/src/pages/ResultPage.tsx`
- 创建：`frontend/user-app/src/styles.css`
- 修改：`frontend/user-app/src/main.tsx`
- 测试：`frontend/user-app/src/pages/__tests__/PersonFilterPage.test.tsx`
- 测试：`frontend/user-app/src/pages/__tests__/ResultPage.test.tsx`
- 测试：`frontend/user-app/src/pages/__tests__/HomePage.test.tsx`

- [ ] **步骤 1：编写失败的用户前台测试**

更新测试，使其验证：

- 提交后调用 `createJob("person_filter")`。
- UI 不显示 `JOB-123456` 和 `token-123`。
- 轮询状态后显示进度条、关键日志。
- completed 且 `download_ready` 时显示“下载结果压缩包”链接。

- [ ] **步骤 2：运行用户前台测试验证失败**

运行：`npm test -- --run src/pages/__tests__/PersonFilterPage.test.tsx src/pages/__tests__/ResultPage.test.tsx src/pages/__tests__/HomePage.test.tsx`

工作目录：`frontend/user-app`

预期：FAIL，原因是页面仍显示回执或缺少日志/下载按钮。

- [ ] **步骤 3：实现用户前台**

实现内容：

- `PublicJobStatus` 增加 `progress`、`events`、`download_ready`。
- 增加 `buildJobDownloadUrl(jobCode, accessToken)`。
- `PersonFilterPage` 提交后保存内部凭据并显示处理状态面板。
- `ResultPage` 复用处理状态面板，展示进度、日志、错误和下载。
- `HomePage` 移除查询入口文案。
- `App.tsx` 移除 `/lookup` 路由或重定向到首页。
- `styles.css` 提供响应式控制台视觉样式。

- [ ] **步骤 4：运行用户前台测试验证通过**

运行：`npm test -- --run src/pages/__tests__/PersonFilterPage.test.tsx src/pages/__tests__/ResultPage.test.tsx src/pages/__tests__/HomePage.test.tsx`

工作目录：`frontend/user-app`

预期：PASS。

## 任务 3：管理员后台任务详情和下载

**文件：**
- 修改：`frontend/admin-app/src/api/client.ts`
- 修改：`frontend/admin-app/src/pages/JobsPage.tsx`
- 创建：`frontend/admin-app/src/styles.css`
- 修改：`frontend/admin-app/src/main.tsx`
- 测试：`frontend/admin-app/src/pages/__tests__/JobsPage.test.tsx`

- [ ] **步骤 1：编写失败的管理员前台测试**

更新 `JobsPage.test.tsx`，验证：

- 列表展示任务进度和状态。
- 点击“详情”调用 `getAdminJob`。
- 详情面板展示事件日志。
- completed 且 `download_ready` 时显示“下载输出结果”链接。
- failed 任务仍可重试，running 任务仍可取消。

- [ ] **步骤 2：运行管理员前台测试验证失败**

运行：`npm test -- --run src/pages/__tests__/JobsPage.test.tsx`

工作目录：`frontend/admin-app`

预期：FAIL，原因是详情 API 与详情面板尚未实现。

- [ ] **步骤 3：实现管理员后台**

实现内容：

- `AdminJob` 增加 `progress`、`download_ready`、`result_zip_available`。
- 新增 `AdminJobDetail`、`getAdminJob(jobId)`、`buildAdminJobDownloadUrl(jobId)`。
- `JobsPage` 加载列表后默认选择第一项，点击详情刷新详情。
- 详情面板展示基础信息、日志、错误和下载入口。
- 保留取消与重试动作。
- `styles.css` 提供后台侧栏、表格、详情面板和状态徽标。

- [ ] **步骤 4：运行管理员前台测试验证通过**

运行：`npm test -- --run src/pages/__tests__/JobsPage.test.tsx`

工作目录：`frontend/admin-app`

预期：PASS。

## 任务 4：全量验证与文档同步

**文件：**
- 按实际路由/API 变化修改：`README.md`
- 按实际路由/API 变化修改：`AGENTS.md`

- [ ] **步骤 1：检查端口、路由、路径和环境变量变化**

确认新增路由：

- `GET /api/jobs/{job_code}/download`
- `GET /api/admin/jobs/{job_id}`
- `GET /api/admin/jobs/{job_id}/download`

如果实现与建议路径一致，更新 README 与 AGENTS 的接口说明。

- [ ] **步骤 2：运行全量验证**

运行：

```bash
python -m pytest tests/backend -v
```

运行：

```bash
npm test
npm run build
```

工作目录分别为 `frontend/user-app` 与 `frontend/admin-app`。

- [ ] **步骤 3：查看 diff 并提交**

运行：

```bash
git diff
git status --short
```

使用中文 Conventional Commits 提交实际改动。

