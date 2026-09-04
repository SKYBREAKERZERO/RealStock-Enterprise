FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 创建非 root 用户
RUN addgroup --system realstock \
    && adduser --system --ingroup realstock realstock

# 项目依赖
COPY pyproject.toml ./

# Python packages
COPY libs ./libs
COPY services ./services

# 安装 RealStock 及其运行时依赖
RUN python -m pip install --upgrade pip \
    && python -m pip install .

# 切换到非 root 用户
USER realstock

EXPOSE 8000

