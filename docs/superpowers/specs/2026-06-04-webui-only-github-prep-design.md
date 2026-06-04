# WebUI Only GitHub 仓库整理设计

**日期：** 2026-06-04

## 1. 背景

当前仓库的真实产品形态是基于 Gradio 的 WebUI 推理与归档工具，而不是同时面向 WebUI 与 CLI 的双入口项目。仓库中仍包含：

- CLI 入口 `infer_link.py`
- 与主产品无关的一次性脚本
- 不适合进入公开仓库的模型权重文件
- 与当前实现不完全一致的 README 与容器说明

本次工作的目标是将仓库整理为适合公开发布到 GitHub 的 `WebUI-only` 版本，确保产品定位、目录边界、文档说明与实际代码一致。

## 2. 目标

- 移除 CLI 路径，只保留 WebUI 访问方式。
- 移除与主产品无关的一次性脚本。
- 移除不应提交到公开仓库的模型权重文件。
- 保留最小必要的示例类别文件，方便使用者理解模型 sidecar 约定。
- 统一 README、Dockerfile、`docker-compose.yml` 与当前产品行为。
- 补齐公开仓库需要的忽略规则与目录占位。

## 3. 非目标

本次不包含以下内容：

- 不重构 `webui/processing.py` 的推理逻辑。
- 不新增 CLI 的替代实现。
- 不新增 CI、测试框架或自动化发布流程。
- 不新增 License。
- 不引入 FiftyOne、MongoDB 或其他新组件。

## 4. 用户确认的边界

用户已明确确认以下决策：

- CLI 入口应被彻底删除，而不是保留但不对外暴露。
- `models/` 中保留少量非权重示例文件（如 `.names`、`.txt`），移除所有 `.onnx`。
- 与主流程无关的一次性脚本一并删除，而不是迁移到 `scripts/`。
- 仓库按公开 GitHub 仓库标准整理。

## 5. 现状判断

### 5.1 真实入口

当前用户使用入口已经是 WebUI：

- `python -m webui.app`
- Docker 容器启动后访问 Gradio 页面

`infer_link.py` 只是额外的命令行入口，不再符合产品定位。

### 5.2 真实核心模块

核心实现主要集中在：

- `webui/app.py`：页面与任务发起
- `webui/job_manager.py`：推理任务管理
- `webui/infer_worker.py`：独立 worker 进程
- `webui/processing.py`：图片收集、预处理、推理、后处理、落盘、打包
- `webui/utils.py`：路径与日志辅助

### 5.3 公开仓库风险

当前仓库若直接公开，存在以下问题：

- 模型权重文件过大，不适合直接纳入版本控制。
- README 同时描述 WebUI 与 CLI，产品定位不够清晰。
- 容器访问说明与实际端口映射存在漂移。
- 根目录存在一次性脚本，会削弱仓库的产品边界与可维护性。
- 缺少明确的 `.gitignore`，后续容易误提交图片输出、缓存文件与模型权重。

## 6. 设计方案

本次采用“中度收敛”方案：只做和“公开、纯 WebUI 仓库”直接相关的整理，不改动推理核心行为。

### 6.1 删除的内容

以下文件将从仓库中删除：

- `infer_link.py`
- `move.py`
- `rename.py`
- `merge_images.py`

删除原则：

- 只移除不再需要、且与主产品定位不一致的入口或脚本。
- 不删除 `webui/` 下的推理与页面逻辑。

### 6.2 保留的内容

以下内容保留：

- `webui/` 全部核心代码
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `models/` 中的示例类别文件（`.names`、`.txt`）

保留原则：

- 保留运行 WebUI 所需的一切代码与配置。
- 保留对模型类别 sidecar 机制有说明价值的轻量文件。

### 6.3 模型与数据目录策略

仓库应只保留目录约定与轻量示例，不保留实际大模型或业务图片数据。

具体策略：

- 删除 `models/` 中全部 `.onnx` 文件。
- 保留 `models/` 中少量 `.names`、`.txt` 示例文件。
- 为 `images/` 及必要子目录保留 Git 占位文件，便于新用户 clone 后直接理解目录结构。
- 使用 `.gitignore` 忽略：
  - `models/*.onnx`
  - `images/` 运行数据与输出
  - Python 缓存、临时文件、压缩产物

### 6.4 容器与启动说明

`Dockerfile` 与 `docker-compose.yml` 需要与 `WebUI-only` 定位完全一致。

调整方向：

- `Dockerfile` 去掉对 `infer_link.py` 的复制。
- `docker-compose.yml` 去掉对 `infer_link.py` 的挂载。
- README 中只保留 WebUI 启动与访问路径说明。
- README 中的访问地址必须与 `docker-compose.yml` 中的端口映射一致。

### 6.5 README 重写原则

README 需要从“功能清单式说明”改成“公开仓库的最小上手文档”。

至少覆盖以下信息：

- 项目定位：基于 WebUI 的 ONNX 推理与归档工具
- 核心能力：上传/选择模型、选择图片目录、按类别归档、导出 zip
- 不包含内容：模型权重与业务图片
- 目录约定：`images/`、`models/`、`webui/`
- 启动方式：本机运行与 Docker 运行
- 使用前准备：将 `.onnx` 模型自行放入 `models/`
- Sidecar 机制：`.names`、`.txt`、`.json`

README 不再出现：

- CLI 用法
- `infer_link.py` 调用示例
- 与当前仓库无关的历史架构表述

## 7. 组件影响

### 7.1 代码文件

- `Dockerfile`：删除 CLI 复制指令
- `docker-compose.yml`：删除 CLI 挂载，校正文档对应关系
- `README.md`：按 WebUI-only 重新组织
- `.gitignore`：新增公开仓库忽略规则

### 7.2 文件系统内容

- 删除不再需要的 Python 脚本
- 删除所有 `.onnx` 权重
- 增加目录占位文件

### 7.3 不改动的稳定区域

以下文件本次不做行为变更：

- `webui/app.py`
- `webui/processing.py`
- `webui/job_manager.py`
- `webui/infer_worker.py`
- `webui/utils.py`

原因是本次目标是“公开发布整理”，不是“产品行为重构”。

## 8. 数据流与运行流

本次整理后，仓库的标准运行流应为：

1. 用户将 `.onnx` 模型手动放入 `models/`
2. 用户将待处理图片放入 `images/` 下的某个目录
3. 用户通过本机命令或 Docker 启动 `webui.app`
4. 用户在浏览器访问 Gradio 页面
5. WebUI 发起推理任务
6. 后台 worker 进程执行推理与归档
7. 结果写入 `images/output/<run_id>/`
8. 用户在页面中查看结果并按需下载 zip

该流程中不再存在命令行推理入口。

## 9. 错误处理与兼容性约束

本次整理不改变现有错误处理语义，但必须保证以下兼容性：

- 删除 CLI 之后，WebUI 启动仍然正常。
- 容器镜像构建不再依赖 `infer_link.py`。
- README 中不出现失效入口或错误端口。
- `.gitignore` 不应误忽略需要保留的示例 sidecar 文件。

## 10. 验证策略

本次整理完成后，至少执行以下验证：

1. 运行 `python3 -m py_compile webui/*.py`，确认 WebUI 代码语法正常。
2. 检查 `Dockerfile` 与 `docker-compose.yml`，确认不再引用 CLI 文件。
3. 检查 `README.md`，确认只描述 WebUI 路径，且端口、目录、运行步骤一致。
4. 检查 `git status`，确认模型权重、图片输出、缓存文件不会作为公开仓库内容被提交。

## 11. 验收标准

当以下条件全部满足时，本次设计视为完成：

- 仓库中不存在 CLI 推理入口与一次性脚本。
- 仓库中不存在 `.onnx` 模型权重。
- `models/` 中保留轻量示例 sidecar 文件。
- README 明确说明这是一个 WebUI-only 项目。
- `Dockerfile` 与 `docker-compose.yml` 不再引用 CLI 文件。
- 存在适合公开仓库的 `.gitignore` 与目录占位策略。
- WebUI 相关 Python 文件可以通过语法级校验。

## 12. 后续实现边界

实现阶段只需要完成与本设计直接相关的仓库整理工作，不应顺手扩展范围，例如：

- 不顺手做推理性能优化
- 不顺手修改推理结果格式
- 不顺手增加测试框架
- 不顺手引入新的部署方式

如果后续需要增强工程化能力，应作为下一轮独立任务处理。
