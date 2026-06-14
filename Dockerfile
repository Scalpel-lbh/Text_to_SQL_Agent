# 文件作用：
# 构建企业数据分析 Agent 的 FastAPI 容器镜像。

# 使用轻量级 Python 3.12 镜像
FROM python:3.12-slim

# 设置容器工作目录
WORKDIR /app

# 禁止 Python 生成 __pycache__ 文件
ENV PYTHONDONTWRITEBYTECODE=1

# 让日志立即输出，便于通过 docker compose logs 查看
ENV PYTHONUNBUFFERED=1

# 先复制依赖文件，利用 Docker 构建缓存
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 将项目代码复制到容器
COPY . .

# 声明 FastAPI 使用的端口
EXPOSE 8000

# 启动 FastAPI 服务
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]