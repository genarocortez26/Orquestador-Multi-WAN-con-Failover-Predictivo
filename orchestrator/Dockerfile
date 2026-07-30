FROM python:3.11-slim

# FIX: "tc" NO es un paquete de Debian, es un binario que viene DENTRO de iproute2.
# El error "E: Unable to locate package tc" venía de listarlo acá.
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iptables \
    iputils-ping \
    conntrack \
    procps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# NOTA (Debian trixie): iptables usa backend nftables. En hosts Linux modernos anda.
# Si en alguna máquina las reglas "no matchean", descomentar el fallback legacy:
# RUN update-alternatives --set iptables /usr/sbin/iptables-legacy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY train_model.py .

CMD ["python", "-m", "app.main"]
