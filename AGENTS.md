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

## 提交与 PR 指南
- 提交信息保持简洁并用祈使句（如 “Add Mongo write batching”），避免不相关变更混入。
- PR 描述应包含改动范围、执行的测试命令、端口/路径变更，并在相关时附上 UI 或日志截图，关联对应 issue。
