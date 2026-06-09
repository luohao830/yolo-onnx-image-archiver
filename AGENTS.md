# 仓库指南（请注意：此仓库的后续回复一律使用中文）

## 项目结构与路径
- 根目录包含 Docker 编排文件（`docker-compose.yml`、`Dockerfile`）以及架构说明文档（`项目架构文档：基于 YOLOv5 与 FiftyOne 的大规模图像检索系统.md`）。
- 服务挂载目录：`images/`（输入媒资）、`models/`（YOLO 权重）、`fo_data/`（MongoDB 持久化）、`webui/`（Gradio/FiftyOne 代码）、`scripts/`（脚本工具）。请保持这些宿主路径稳定，避免绑定失效。
- `webui/` 预计包含 `app.py`（UI 入口）、`processing.py`（批量推理与格式化）、`utils.py`（日志/路径辅助），与架构文档保持一致。

## 构建、运行与开发
- 构建镜像：`docker-compose build`（已含代理参数）。
- 无头启动（Mongo + app）：`docker-compose up -d`；停止：`docker-compose down`（数据经挂载目录持久化）。
- 观察日志：`docker-compose logs -f app`。调试交互 shell：`docker-compose exec app bash`。
- GPU 绑定默认使用 `docker-compose.yml` 中的设备索引 `1`；如需更换显卡，调整 `deploy.resources.reservations.devices[0].device_ids`。

## 编码风格与命名
- Python 遵循 PEP 8：4 空格缩进，函数/文件用 `snake_case`，类用 `CapWords`，尽量保持函数小而纯。
- 脚本文件使用动词前缀命名（如 `sync_models.py`、`scan_images.py`），并通过参数传入路径/阈值，避免硬编码。
- 公共辅助函数请添加简短 docstring；多用日志少用 print，保持 Gradio 输出整洁。

## 测试指南
- 在代码附近添加聚焦测试，如 `webui/tests/test_processing.py` 覆盖 bbox 转换、跳过/覆盖逻辑、基于生成器的批处理。
- 在容器内运行测试以匹配依赖：`docker-compose exec app pytest /webui/tests`。
- 如需新增测试依赖，请在 `Dockerfile` 声明以确保镜像可复现。使用位于 `webui/tests/data` 的小型夹具数据，避免全量数据集。

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
- `pnpm test`：通过 / 失败，失败原因为 ...
- `pnpm lint`：通过 / 失败，失败原因为 ...

## 端口 / 路径变更
- 无
```

如有变更，需明确列出：

```md
## 端口 / 路径变更
- 新增路由：`/api/tasks/:id/retry`
- 修改配置：`runtime.workers.timeout`
- 废弃配置：`database.task_timeout_minutes`
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
