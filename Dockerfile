FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config.py .
COPY data/ ./data/

EXPOSE 5005

CMD ["gunicorn", "--bind", "0.0.0.0:5005", "--workers", "1", "--worker-class", "gthread", "--threads", "4", "--timeout", "600", "app:create_app()"]
