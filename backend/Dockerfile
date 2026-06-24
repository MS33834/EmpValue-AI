FROM python:3.11-slim

WORKDIR /app

# 安装 chromadb 等依赖可能需要的系统库
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
