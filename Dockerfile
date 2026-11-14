FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py enhancements.py ./
COPY static/ ./static/
EXPOSE 8000
ENV SMALLBIZ_DB=/data/demo.sqlite3
ENV SMALLBIZ_KEY_FILE=/data/.smallbiz-fernet-key
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
