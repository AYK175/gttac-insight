FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY gttac_insight/ gttac_insight/
COPY docs/ docs/
COPY .rag_index/ .rag_index/

ENV RAG_DOCS_DIR=docs
ENV RAG_INDEX_DIR=.rag_index

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
