# 仓库指南（请注意：此仓库的后续回复一律使用中文）

## 项目定位

基于 Gradio 的单机 YOLO ONNX 推理与归档工具：用户在浏览器中上传或选择 `.onnx` 模型、上传图片或 `.zip` 压缩包，选择关注类别后运行推理，按类别归档到输出目录，并支持画框、YOLO `labels/txt` 导出与结果 `zip` 打包下载。

## 协作与实现原则

- 禁止自作主张做“最小化实现”而忽略用户设计要求；必须按用户确认的目标架构最大努力完成。
- 禁止过度保守；用户提出提高效率、多个 worktree 并行推进时，必须给出可行、清晰的并行方案。
- 禁止未讨论充分就直接改代码；架构和模块设计未确认前，只做文档讨论和设计沉淀。

## 常用命令

### Docker Compose 启动（生产/集成验证）

```bash
mkdir -p models
docker compose build
docker compose up -d
```

访问：`http://127.0.0.1:7860/`

常用运维：

```bash
docker compose ps
docker compose logs -f webui
docker compose down
```

### 本机开发

```bash
python -m pip install -r requirements.txt
python -m webui.app
```

入口 `webui/app.py` 的 `main()`，默认监听 `0.0.0.0:7860`。

### 测试

webui 纯函数测试：

```bash
python -m pytest tests/webui -v
```

运行单个测试文件或用例：

```bash
python -m pytest tests/webui/test_archive_ingest.py -v
python -m pytest tests/webui/test_label_and_postprocess.py::test_sanitize_label_passes_clean_text -v
```

语法校验：

```bash
python3 -m py_compile webui/*.py
```

### 健康检查

无独立健康检查端点；浏览器访问 `http://127.0.0.1:7860/` 即为 WebUI 首页。

## 项目结构与路径

- `webui/`：Gradio 页面与推理工具链。`app.py` 为页面入口；`job_manager.py` 管理多 worker 任务队列；`infer_worker.py` 是独立推理 worker 进程并负责 GPU 检测/绑定；`processing.py` 是推理内核 `run_inference` 与打包 `package_output_dir`；`archive_ingest.py` 处理 `.zip` 解压；`utils.py`/`label_utils.py`/`yolo_postprocess.py` 为辅助与后处理。
- `models/` 保存 `.onnx` 模型与同名 sidecar（`.names`/`.txt`/`.json`）；Docker 中挂载为 `/data/models`。
- `images/` 是图片与输出工作区，Docker 中挂载为 `/data/images`；其下 `uploads/` 存上传图片与解压结果，`output/<run_id>/` 存推理归档与打包 zip。
- `tests/webui/` 保存 webui 纯函数测试；不要提交运行产物。

## 当前架构状态

- 仓库为单机 Gradio 工具，唯一运行入口为 `python -m webui.app`。
- Docker Compose 单服务 `webui`，暴露 7860，挂载 NVIDIA GPU（默认仅 GPU 0）。

## 模块分层（webui/）

- `app.py`：Gradio 页面与事件编排（上传模型/图片/zip、运行推理、单独打包）。
- `job_manager.py`：`InferenceJobManager` 多 worker 池，按可见 GPU 数创建 worker 进程，任务 round-robin 分发。
- `infer_worker.py`：推理 worker 循环与 `detect_available_gpus()`；通过 `CUDA_VISIBLE_DEVICES` 限定单 worker 可见 GPU 实现任务级多 GPU 分流。
- `processing.py`：`run_inference` 推理内核（letterbox/ONNX session/NMS/按类别硬链接或复制归档/画框/txt 导出），`package_output_dir` 打包（`ZIP_STORED`，等价 `zip -r -0`）。
- `archive_ingest.py`：`extract_upload_archive` 安全解压 `.zip`（路径遍历防护 + 原子替换，仅保留受支持图片扩展名）。
- `utils.py`：路径/文件名/日志辅助，`resolve_images_dir` 兼容相对路径与宿主机绝对路径换算。

## 调度与推理流程

1. 用户在 WebUI 选择模型、填入图片目录（相对 `images/`、上传 zip 自动回填、或宿主机绝对路径），设置推理参数。
2. `run_job` 经 `resolve_images_dir` 解析为容器内目录，组装 payload 提交给 `InferenceJobManager.submit`。
3. `InferenceJobManager` 按可见 GPU 数创建 N 个 worker 进程，任务 round-robin 分发到某 worker 的请求队列；该 worker 已通过 `CUDA_VISIBLE_DEVICES` 绑定特定 GPU。
4. worker 调用 `run_inference` 执行推理，经进度回调把 `InferenceProgress` 写回事件队列，WebUI 推进推理进度条。
5. 推理完成后按类别把原图硬链接/复制归档到 `output/<run_id>/<类别>/images`、`labels`、`<类别>_画框`。
6. 勾选打包时，`package_output_dir` 用 `ZIP_STORED` 打成不压缩 zip，WebUI 用独立的打包进度条显示进度并产出可下载文件。

## 多 GPU 策略

- `docker-compose.yml` 默认 `device_ids: ["0"]`，仅挂载 GPU 0；改为 `["0","1"]` 即可挂载双 GPU。
- `detect_available_gpus()` 依据 `CUDA_VISIBLE_DEVICES` 计数可见 GPU：
  - 可见 ≥ 2：开启任务级多 GPU 分流，多个 worker 各绑定一块 GPU 并发执行任务。
  - 可见 = 1：单 worker 落 GPU 0。
  - 0（无 CUDA EP）：1 个 CPU worker，自动回退。
- 单任务推理内部仍是单 GPU 单 batch（非 batch 级切分）。

## 宿主机路径兼容

- `resolve_images_dir(path_text, images_dir, host_images_dir)`：
  - 相对路径 → `images_dir/rel`。
  - 宿主机绝对路径 → 以 `host_images_dir` 为前缀换算为 `images_dir` 下路径（`HOST_IMAGES_DIR` 环境变量，默认与 `IMAGES_DIR` 相同）。
  - 容器内绝对路径 → 直接 resolve。
- 在 `docker-compose.yml` 中把 `volumes` 的左侧改为实际宿主机绝对路径，并把 `HOST_IMAGES_DIR` 改为同一路径即可。

## 上传与解压

- `.zip` 压缩包每次重新上传并解压到 `images/uploads/<run_id>/` 下的独立子目录，不做 hash 复用或缓存。
- 解压仅保留受支持的图片扩展名（`.jpg/.jpeg/.png/.bmp/.tif/.tiff/.webp/.gif`），含路径遍历防护。
- 解压完成后自动把解压目录（相对 `images/`）回填到推理输入框，无需手动输入。

## 编码风格与命名

- Python 遵循 PEP 8：4 空格缩进，函数与文件使用 `snake_case`，类使用 `CapWords`。
- 公共辅助函数添加简短 docstring 或清晰类型签名；日志优先于 `print`。

## 配置与运行时约束

- 环境变量：`IMAGES_DIR`（容器内图片工作区，默认 `/data/images`）、`HOST_IMAGES_DIR`（宿主机侧 images 路径，用于绝对路径换算，默认同 `IMAGES_DIR`）、`MODELS_DIR`（默认 `/data/models`）、`TZ`（默认 `Asia/Shanghai`）。
- 容器时区设为 `Asia/Shanghai`（UTC+8），日志与 `now_run_id` 目录时间戳均使用本地时间。
- GPU 默认仅挂载 0；需双 GPU 加速时把 `docker-compose.yml` 的 `device_ids` 改为 `["0","1"]`，并不要同时设置 `count`。
- 修改端口、挂载路径、环境变量或模型路径语义时，必须同步更新 `README.md`、`AGENTS.md` 和 PR 描述。

## 模型管理

- 模型文件放在 `MODELS_DIR`，可带同名 `.names`/`.txt`/`.json` sidecar 描述类别名。
- WebUI“上传模型”页可上传 `.onnx` 并刷新列表；模型类别名优先取 sidecar，无 sidecar 时使用 `cls_id`。

## 测试指南

- webui 测试：`python -m pytest tests/webui -v`。
- 修改推理执行、归档解压或打包时，优先覆盖 `test_archive_ingest.py`、`test_package.py`、`test_gpu_assign.py`、`test_label_and_postprocess.py`。
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
feat(webui): 支持上传 zip 压缩包自动解压回填推理目录

上传图片页支持 .zip 压缩包，后台调用 extract_upload_archive 自动解压仅保留受支持图片，并把解压目录回填到推理输入框。

技术方案：
- 新增 webui/archive_ingest.py，移植安全解压逻辑（路径遍历防护 + 原子替换）
- webui/app.py 区分 zip 与图片，解压后回填相对目录
- 补充 tests/webui/test_archive_ingest.py

影响范围：
- webui 推理工具链
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
- `python -m pytest tests/webui -v`：通过 / 失败，失败原因为 ...

## 端口 / 路径变更
- 无
```

如有变更，需明确列出：

```md
## 端口 / 路径变更
- 新增环境变量：`HOST_IMAGES_DIR`
- 修改挂载：`/data/xxx/images:/data/images`
- 修改端口：对外暴露 `7860`
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

- `README.md`：更详细的使用说明、环境变量、启动方式与输出结构。