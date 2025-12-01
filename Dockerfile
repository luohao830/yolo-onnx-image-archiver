# 1. 使用官方 YOLOv5 镜像
FROM ultralytics/yolov5:v7.0

# 2. 接收代理参数 (虽然用国内源不需要代理，但留着防止其他包需要)
ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY

# 3. 安装 FiftyOne 和 Gradio
# === 关键修改：加入清华源 -i https://pypi.tuna.tsinghua.edu.cn/simple ===
RUN pip install --no-cache-dir --upgrade pip && \
    pip install fiftyone gradio -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 设置工作目录
WORKDIR /usr/src/app