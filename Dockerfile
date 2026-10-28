FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server /app/server
RUN useradd -m studio && mkdir /data && chown studio:studio /data
USER studio
ENV STUDIO_DATA_DIR=/data
CMD ["uvicorn", "server.core:app", "--host", "0.0.0.0", "--port", "8080"]
