# WebUI-only GitHub 仓库整理实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将仓库整理为只通过 WebUI 访问、适合公开提交到 GitHub 的版本。

**架构：** 保留 `webui/` 作为唯一产品入口，移除 CLI 和一次性脚本。用 `.gitignore` 和目录占位表达公开仓库边界，用 README、Dockerfile、`docker-compose.yml` 对齐实际运行方式。

**技术栈：** Python、Gradio、ONNXRuntime、Docker Compose、Git。

---

## 文件结构

- 修改：`README.md`，重写为 WebUI-only 上手文档。
- 修改：`Dockerfile`，移除 `infer_link.py` 复制指令。
- 修改：`docker-compose.yml`，移除 `infer_link.py` 挂载。
- 创建：`.gitignore`，忽略模型权重、图片数据、运行输出和缓存。
- 创建：`images/.gitkeep`、`images/uploads/.gitkeep`、`images/output/.gitkeep`，保留目录约定。
- 删除：`infer_link.py`、`move.py`、`rename.py`、`merge_images.py`。
- 删除：`models/*.onnx`，保留 `.names`、`.txt` 示例 sidecar。
- 验证：`webui/*.py`，只做语法校验，不修改核心逻辑。

## 任务 1：建立红灯检查

**文件：**
- 检查：`README.md`
- 检查：`Dockerfile`
- 检查：`docker-compose.yml`
- 检查：`models/`
- 检查：根目录脚本

- [ ] **步骤 1：运行 CLI 引用扫描，确认当前失败**

```bash
rg -n "infer_link|CLI|命令行" README.md Dockerfile docker-compose.yml
```

预期：命中 README、Dockerfile、`docker-compose.yml` 中的旧 CLI 引用。

- [ ] **步骤 2：运行待删除文件扫描，确认当前失败**

```bash
find . -maxdepth 1 -type f \( -name 'infer_link.py' -o -name 'move.py' -o -name 'rename.py' -o -name 'merge_images.py' \) -print
```

预期：输出 4 个待删除文件。

- [ ] **步骤 3：运行模型权重扫描，确认当前失败**

```bash
find models -maxdepth 1 -type f -name '*.onnx' -print
```

预期：输出当前 `.onnx` 权重文件。

## 任务 2：移除旧入口和大文件

**文件：**
- 删除：`infer_link.py`
- 删除：`move.py`
- 删除：`rename.py`
- 删除：`merge_images.py`
- 删除：`models/*.onnx`

- [ ] **步骤 1：删除 CLI 和一次性脚本**

```bash
rm infer_link.py move.py rename.py merge_images.py
```

预期：根目录不再存在这些脚本。

- [ ] **步骤 2：删除模型权重文件**

```bash
rm models/*.onnx
```

预期：`models/` 下只剩 `.names`、`.txt` 等轻量 sidecar 文件。

- [ ] **步骤 3：重新运行删除检查**

```bash
find . -maxdepth 1 -type f \( -name 'infer_link.py' -o -name 'move.py' -o -name 'rename.py' -o -name 'merge_images.py' \) -print
find models -maxdepth 1 -type f -name '*.onnx' -print
```

预期：两条命令都没有输出。

## 任务 3：更新容器配置

**文件：**
- 修改：`Dockerfile`
- 修改：`docker-compose.yml`

- [ ] **步骤 1：修改 `Dockerfile`**

移除以下行：

```dockerfile
COPY infer_link.py /app/infer_link.py
```

保留：

```dockerfile
COPY webui /app/webui
ENTRYPOINT ["python3", "-m", "webui.app"]
```

- [ ] **步骤 2：修改 `docker-compose.yml`**

移除以下挂载：

```yaml
- ./infer_link.py:/app/infer_link.py
```

保留：

```yaml
- ./images:/data/images
- ./models:/data/models
- ./webui:/app/webui
```

- [ ] **步骤 3：验证容器配置不再引用 CLI**

```bash
rg -n "infer_link|CLI|命令行" Dockerfile docker-compose.yml
```

预期：没有输出。

## 任务 4：新增公开仓库边界

**文件：**
- 创建：`.gitignore`
- 创建：`images/.gitkeep`
- 创建：`images/uploads/.gitkeep`
- 创建：`images/output/.gitkeep`

- [ ] **步骤 1：创建 `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/

images/*
!images/.gitkeep
!images/uploads/
!images/uploads/.gitkeep
!images/output/
!images/output/.gitkeep

models/*.onnx
*.zip
*.tar
*.tar.gz
*.7z
```

- [ ] **步骤 2：创建目录占位文件**

```bash
mkdir -p images/uploads images/output
touch images/.gitkeep images/uploads/.gitkeep images/output/.gitkeep
```

- [ ] **步骤 3：验证忽略规则**

```bash
git status --short --ignored images models
```

预期：`.gitkeep` 可见，运行数据和 `.onnx` 权重不会作为普通待提交文件出现。

## 任务 5：重写 README

**文件：**
- 修改：`README.md`

- [ ] **步骤 1：替换 README 内容**

README 必须覆盖：

```markdown
# YOLO ONNX WebUI 推理归档工具

## 项目定位

## 功能

## 目录结构

## 准备模型和图片

## Docker 运行

## 本机运行

## 类别文件 sidecar

## 输出结构

## 公开仓库说明
```

- [ ] **步骤 2：删除 CLI 文案**

README 中不得出现：

```text
infer_link.py
CLI
命令行推理
```

- [ ] **步骤 3：验证 README**

```bash
rg -n "infer_link|CLI|命令行" README.md
rg -n "localhost:57860|57860:7860|python -m webui.app" README.md docker-compose.yml
```

预期：第一条没有输出；第二条能看到 WebUI 端口和本机启动说明。

## 任务 6：最终验证与提交准备

**文件：**
- 验证：`webui/*.py`
- 验证：全仓库状态

- [ ] **步骤 1：语法校验**

```bash
python3 -m py_compile webui/*.py
```

预期：退出码为 0。

- [ ] **步骤 2：全仓库旧入口扫描**

```bash
rg -n "infer_link|CLI|命令行" --glob '!docs/superpowers/**'
```

预期：没有输出。

- [ ] **步骤 3：权重文件扫描**

```bash
find models -maxdepth 1 -type f -name '*.onnx' -print
```

预期：没有输出。

- [ ] **步骤 4：检查 Git 状态**

```bash
git status --short
```

预期：只包含 WebUI 主产品代码、文档、配置、示例 sidecar、目录占位和删除记录。

- [ ] **步骤 5：提交实现变更**

```bash
git add README.md Dockerfile docker-compose.yml requirements.txt webui models .gitignore images docs/superpowers/plans/2026-06-04-webui-only-github-prep.md
git add -u infer_link.py move.py rename.py merge_images.py models
git commit -m "chore: prepare WebUI-only GitHub repository"
```

预期：生成一个整理提交；如果 Git 元数据写入受限，需要带授权重试提交命令。
