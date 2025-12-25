# 轻量化推理环境：仅 ONNXRuntime-GPU + Gradio
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ARG HTTP_PROXY
ARG HTTPS_PROXY
ENV HTTP_PROXY=$HTTP_PROXY
ENV HTTPS_PROXY=$HTTPS_PROXY

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/app

RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir \
      numpy opencv-python-headless onnxruntime-gpu gradio

COPY app ./app
COPY webui ./webui
COPY yolo-fiftyone.md ./yolo-fiftyone.md

EXPOSE 7860

CMD ["python3", "webui/app.py"]
