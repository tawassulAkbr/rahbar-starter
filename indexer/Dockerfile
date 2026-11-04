FROM python:3.12.7-slim

# Install system dependencies for OCR and PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd -r indexergroup -g 10002 && useradd -r -u 10002 -g indexergroup -m -d /home/indexeruser indexeruser

WORKDIR /indexer

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline/ ./pipeline

USER indexeruser

CMD ["python", "-m", "pipeline.run"]
