FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY traffic.py .

CMD ["python", "traffic.py"]
