# 用户前台实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建面向用户的前台站点，支持人员筛选模式、高级模式、任务凭证回显、任务查询和结果下载。

**架构：** 使用 `frontend/user-app/` 承载独立前端，调用后端公共 API 完成任务创建、文件上传、进度轮询和结果下载。首页以人员筛选模式为主入口，高级模式在第二层暴露已发布模型和有限参数。

**技术栈：** React、TypeScript、Vite、React Testing Library、Vitest、FastAPI 公共 API。

---

## 文件结构

- 创建：`frontend/user-app/package.json`，声明前台依赖与脚本。
- 创建：`frontend/user-app/tsconfig.json`，配置 TypeScript。
- 创建：`frontend/user-app/vite.config.ts`，配置 Vite。
- 创建：`frontend/user-app/src/main.tsx`，挂载应用。
- 创建：`frontend/user-app/src/App.tsx`，应用壳与路由。
- 创建：`frontend/user-app/src/api/client.ts`，封装公共 API 调用。
- 创建：`frontend/user-app/src/pages/HomePage.tsx`，展示两种模式入口。
- 创建：`frontend/user-app/src/pages/PersonFilterPage.tsx`，人员筛选提交页。
- 创建：`frontend/user-app/src/pages/AdvancedModePage.tsx`，高级模式提交页。
- 创建：`frontend/user-app/src/pages/LookupPage.tsx`，任务凭证查询页。
- 创建：`frontend/user-app/src/pages/ResultPage.tsx`，任务状态与下载页。
- 创建：`frontend/user-app/src/components/ModeCard.tsx`，首页模式卡片。
- 创建：`frontend/user-app/src/components/UploadField.tsx`，统一文件选择控件。
- 创建：`frontend/user-app/src/components/ReceiptPanel.tsx`，展示任务编号与访问口令。
- 创建：`frontend/user-app/src/components/StatusTimeline.tsx`，展示任务阶段。
- 创建：`frontend/user-app/src/test/setup.ts`，测试环境初始化。
- 创建：`frontend/user-app/src/pages/__tests__/HomePage.test.tsx`
- 创建：`frontend/user-app/src/pages/__tests__/PersonFilterPage.test.tsx`
- 创建：`frontend/user-app/src/pages/__tests__/AdvancedModePage.test.tsx`
- 创建：`frontend/user-app/src/pages/__tests__/LookupPage.test.tsx`
- 创建：`frontend/user-app/src/pages/__tests__/ResultPage.test.tsx`

## 任务 1：搭建用户前台骨架与 API 客户端

**文件：**
- 创建：`frontend/user-app/package.json`
- 创建：`frontend/user-app/tsconfig.json`
- 创建：`frontend/user-app/vite.config.ts`
- 创建：`frontend/user-app/src/main.tsx`
- 创建：`frontend/user-app/src/App.tsx`
- 创建：`frontend/user-app/src/api/client.ts`
- 测试：`frontend/user-app/src/pages/__tests__/HomePage.test.tsx`

- [ ] **步骤 1：编写失败的首页渲染测试**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "../../App";


it("renders both entry modes on home page", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );

  expect(screen.getByText("人员筛选模式")).toBeInTheDocument();
  expect(screen.getByText("高级模式")).toBeInTheDocument();
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/user-app && npm test -- HomePage.test.tsx`

预期：`frontend/user-app` 尚不存在，测试失败。

- [ ] **步骤 3：创建前台最小骨架**

`frontend/user-app/package.json`：

```json
{
  "name": "user-app",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.30.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

`frontend/user-app/src/App.tsx`：

```tsx
import { Link, Route, Routes } from "react-router-dom";


export function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <main>
            <h1>图片任务平台</h1>
            <Link to="/person-filter">人员筛选模式</Link>
            <Link to="/advanced">高级模式</Link>
          </main>
        }
      />
    </Routes>
  );
}
```

- [ ] **步骤 4：实现 API 客户端占位并验证测试通过**

`frontend/user-app/src/api/client.ts`：

```ts
export async function createJob(mode: "person_filter" | "advanced") {
  return fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  }).then((response) => response.json());
}
```

运行：`cd frontend/user-app && npm test -- HomePage.test.tsx`

预期：测试 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add frontend/user-app
git commit -m "feat: scaffold anonymous user portal"
```

## 任务 2：实现首页与人员筛选模式提交流程

**文件：**
- 创建：`frontend/user-app/src/pages/HomePage.tsx`
- 创建：`frontend/user-app/src/pages/PersonFilterPage.tsx`
- 创建：`frontend/user-app/src/components/ModeCard.tsx`
- 创建：`frontend/user-app/src/components/UploadField.tsx`
- 创建：`frontend/user-app/src/components/ReceiptPanel.tsx`
- 测试：`frontend/user-app/src/pages/__tests__/PersonFilterPage.test.tsx`

- [ ] **步骤 1：编写失败的人员筛选提交流程测试**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { PersonFilterPage } from "../PersonFilterPage";


it("submits person filter job and shows receipt", async () => {
  render(<PersonFilterPage />);

  fireEvent.change(screen.getByLabelText("上传图片或压缩包"), {
    target: { files: [new File(["demo"], "images.zip", { type: "application/zip" })] },
  });
  fireEvent.click(screen.getByRole("button", { name: "开始处理" }));

  await waitFor(() => {
    expect(screen.getByText("任务编号")).toBeInTheDocument();
    expect(screen.getByText("访问口令")).toBeInTheDocument();
  });
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/user-app && npm test -- PersonFilterPage.test.tsx`

预期：`PersonFilterPage` 未定义或点击后无回执。

- [ ] **步骤 3：实现人员筛选模式页面**

`frontend/user-app/src/pages/PersonFilterPage.tsx`：

```tsx
import { useState } from "react";

import { createJob } from "../api/client";
import { ReceiptPanel } from "../components/ReceiptPanel";


export function PersonFilterPage() {
  const [receipt, setReceipt] = useState<null | { job_code: string; access_token: string }>(null);

  async function handleSubmit() {
    const created = await createJob("person_filter");
    setReceipt(created);
  }

  return (
    <section>
      <h2>人员筛选模式</h2>
      <label htmlFor="archive">上传图片或压缩包</label>
      <input id="archive" type="file" />
      <button onClick={handleSubmit}>开始处理</button>
      {receipt ? <ReceiptPanel receipt={receipt} /> : null}
    </section>
  );
}
```

- [ ] **步骤 4：补齐文件上传调用并验证测试通过**

补齐：

```ts
export async function uploadJobInput(jobCode: string, accessToken: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  form.append("access_token", accessToken);
  return fetch(`/api/jobs/${jobCode}/upload`, { method: "POST", body: form });
}
```

运行：`cd frontend/user-app && npm test -- PersonFilterPage.test.tsx`

预期：测试 `PASS`，页面能显示任务编号和访问口令。

- [ ] **步骤 5：Commit**

```bash
git add frontend/user-app/src/pages frontend/user-app/src/components frontend/user-app/src/api
git commit -m "feat: add person filter job submission flow"
```

## 任务 3：实现高级模式和已发布模型选择

**文件：**
- 创建：`frontend/user-app/src/pages/AdvancedModePage.tsx`
- 修改：`frontend/user-app/src/api/client.ts`
- 测试：`frontend/user-app/src/pages/__tests__/AdvancedModePage.test.tsx`

- [ ] **步骤 1：编写失败的高级模式测试**

```tsx
import { render, screen, waitFor } from "@testing-library/react";

import { AdvancedModePage } from "../AdvancedModePage";


it("loads published models for advanced mode", async () => {
  render(<AdvancedModePage />);

  await waitFor(() => {
    expect(screen.getByLabelText("选择模型")).toBeInTheDocument();
    expect(screen.getByText("helmet-person-v1")).toBeInTheDocument();
  });
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/user-app && npm test -- AdvancedModePage.test.tsx`

预期：没有高级模式页面，或没有模型数据。

- [ ] **步骤 3：实现模型获取与高级模式表单**

`frontend/user-app/src/api/client.ts` 增加：

```ts
export async function listPublishedModels() {
  return fetch("/api/jobs/models").then((response) => response.json());
}
```

`frontend/user-app/src/pages/AdvancedModePage.tsx`：

```tsx
import { useEffect, useState } from "react";

import { listPublishedModels } from "../api/client";


export function AdvancedModePage() {
  const [models, setModels] = useState<Array<{ id: number; name: string }>>([]);

  useEffect(() => {
    listPublishedModels().then(setModels);
  }, []);

  return (
    <section>
      <h2>高级模式</h2>
      <label htmlFor="model">选择模型</label>
      <select id="model">
        {models.map((item) => (
          <option key={item.id}>{item.name}</option>
        ))}
      </select>
    </section>
  );
}
```

- [ ] **步骤 4：补齐 `conf`、`iou`、`batch` 控件并验证通过**

运行：`cd frontend/user-app && npm test -- AdvancedModePage.test.tsx`

预期：测试 `PASS`，页面展示模型下拉框和高级参数控件。

- [ ] **步骤 5：Commit**

```bash
git add frontend/user-app/src/pages/AdvancedModePage.tsx frontend/user-app/src/api/client.ts frontend/user-app/src/pages/__tests__/AdvancedModePage.test.tsx
git commit -m "feat: add advanced mode form"
```

## 任务 4：实现任务凭证查询页

**文件：**
- 创建：`frontend/user-app/src/pages/LookupPage.tsx`
- 测试：`frontend/user-app/src/pages/__tests__/LookupPage.test.tsx`

- [ ] **步骤 1：编写失败的凭证查询测试**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LookupPage } from "../LookupPage";


it("looks up a job with job code and access token", async () => {
  render(<LookupPage />);

  fireEvent.change(screen.getByLabelText("任务编号"), { target: { value: "JOB-100" } });
  fireEvent.change(screen.getByLabelText("访问口令"), { target: { value: "secret-token" } });
  fireEvent.click(screen.getByRole("button", { name: "查询任务" }));

  await waitFor(() => {
    expect(screen.getByText("处理中")).toBeInTheDocument();
  });
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/user-app && npm test -- LookupPage.test.tsx`

预期：`LookupPage` 不存在。

- [ ] **步骤 3：实现查询页**

```tsx
import { useState } from "react";

import { getJobStatus } from "../api/client";


export function LookupPage() {
  const [jobCode, setJobCode] = useState("");
  const [accessToken, setAccessToken] = useState("");
  const [result, setResult] = useState<any>(null);

  async function handleLookup() {
    setResult(await getJobStatus(jobCode, accessToken));
  }

  return (
    <section>
      <label htmlFor="job-code">任务编号</label>
      <input id="job-code" value={jobCode} onChange={(event) => setJobCode(event.target.value)} />
      <label htmlFor="access-token">访问口令</label>
      <input id="access-token" value={accessToken} onChange={(event) => setAccessToken(event.target.value)} />
      <button onClick={handleLookup}>查询任务</button>
      {result ? <div>{result.status_label}</div> : null}
    </section>
  );
}
```

- [ ] **步骤 4：验证查询成功、凭证错误、任务不存在 3 类用例**

运行：`cd frontend/user-app && npm test -- LookupPage.test.tsx`

预期：3 类测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add frontend/user-app/src/pages/LookupPage.tsx frontend/user-app/src/pages/__tests__/LookupPage.test.tsx
git commit -m "feat: add anonymous job lookup page"
```

## 任务 5：实现结果页进度轮询与下载状态

**文件：**
- 创建：`frontend/user-app/src/pages/ResultPage.tsx`
- 创建：`frontend/user-app/src/components/StatusTimeline.tsx`
- 测试：`frontend/user-app/src/pages/__tests__/ResultPage.test.tsx`

- [ ] **步骤 1：编写失败的结果页轮询测试**

```tsx
import { render, screen, waitFor } from "@testing-library/react";

import { ResultPage } from "../ResultPage";


it("polls job progress until download is available", async () => {
  render(<ResultPage jobCode="JOB-200" accessToken="token-200" />);

  await waitFor(() => {
    expect(screen.getByText("排队中")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "下载结果" })).toHaveAttribute("href", "/api/jobs/JOB-200/download");
  });
});
```

- [ ] **步骤 2：运行测试验证当前失败**

运行：`cd frontend/user-app && npm test -- ResultPage.test.tsx`

预期：没有结果页实现，或不会轮询。

- [ ] **步骤 3：实现状态轮询与时间线**

`frontend/user-app/src/pages/ResultPage.tsx`：

```tsx
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { getJobStatus } from "../api/client";
import { StatusTimeline } from "../components/StatusTimeline";


export function ResultPage({
  jobCode: jobCodeProp,
  accessToken: accessTokenProp,
}: {
  jobCode?: string;
  accessToken?: string;
}) {
  const { jobCode: routeJobCode = "" } = useParams();
  const [searchParams] = useSearchParams();
  const jobCode = jobCodeProp ?? routeJobCode;
  const accessToken = accessTokenProp ?? searchParams.get("access_token") ?? "";
  const [job, setJob] = useState<any>(null);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      const next = await getJobStatus(jobCode, accessToken);
      setJob(next);
      if (next.status === "completed" || next.status === "failed") {
        window.clearInterval(timer);
      }
    }, 1500);

    return () => window.clearInterval(timer);
  }, [jobCode, accessToken]);

  return job ? <StatusTimeline status={job.status} /> : <p>正在加载任务中</p>;
}
```

- [ ] **步骤 4：补齐完成、失败、过期三种状态展示并验证通过**

运行：`cd frontend/user-app && npm test -- ResultPage.test.tsx`

预期：轮询测试、失败状态测试、过期状态测试全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add frontend/user-app/src/pages/ResultPage.tsx frontend/user-app/src/components/StatusTimeline.tsx frontend/user-app/src/pages/__tests__/ResultPage.test.tsx
git commit -m "feat: add job result polling page"
```

## 任务 6：构建产物与开发验证

**文件：**
- 修改：`frontend/user-app/src/App.tsx`
- 验证：`frontend/user-app`

- [ ] **步骤 1：补齐路由**

路由最少包含：

```tsx
<Route path="/" element={<HomePage />} />
<Route path="/person-filter" element={<PersonFilterPage />} />
<Route path="/advanced" element={<AdvancedModePage />} />
<Route path="/lookup" element={<LookupPage />} />
<Route path="/results/:jobCode" element={<ResultPage />} />
```

- [ ] **步骤 2：运行前台测试**

运行：`cd frontend/user-app && npm test`

预期：全部 `PASS`。

- [ ] **步骤 3：运行打包验证**

运行：`cd frontend/user-app && npm run build`

预期：输出 `dist/`，构建成功。

- [ ] **步骤 4：Commit**

```bash
git add frontend/user-app/src/App.tsx
git commit -m "build: verify anonymous user portal"
```
