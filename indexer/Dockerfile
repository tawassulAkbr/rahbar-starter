FROM python:3.12.3-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10002 rahbarindexer \
    && useradd --system --uid 10002 --gid 10002 --no-create-home rahbarindexer
COPY indexer/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY indexer/pipeline ./pipeline
COPY corpus /corpus
RUN mkdir -p /corpus && chown 10002:10002 /corpus
USER 10002:10002
CMD ["python", "-m", "pipeline.run"]
