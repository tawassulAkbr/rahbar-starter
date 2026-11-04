FROM python:3.12.7-slim

# Create dedicated non-root user and group
RUN groupadd -r appgroup -g 10001 && useradd -r -u 10001 -g appgroup -m -d /home/appuser appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

USER appuser
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
