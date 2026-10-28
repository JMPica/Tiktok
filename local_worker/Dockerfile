FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt requests
COPY server /app/server
COPY local_worker /app/local_worker
RUN useradd -m -u 10001 blau
USER blau
CMD ["python", "-m", "local_worker.agent"]
