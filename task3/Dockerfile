FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN mkdir -p /data
ENV TASK3_DB_PATH=/data/proposals.db
EXPOSE 8002
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8002"]
