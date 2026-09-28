FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fabletics/ fabletics/
COPY server/ server/

RUN mkdir -p /app/data

ENV HOST=0.0.0.0
ENV PORT=8090

EXPOSE 8090

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8090"]
