# Stateless Multi-Agent Container Image (Local Docker -> Cloud Run & Vertex AI Reasoning Engine)
FROM python:3.11-slim

WORKDIR /workspace

ARG AGENT_GATEWAY_ROOT_CERTIFICATES
RUN if [ -n "$AGENT_GATEWAY_ROOT_CERTIFICATES" ]; then \
      apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
      printf "%b" "$AGENT_GATEWAY_ROOT_CERTIFICATES" | awk 'BEGIN {c=0} /BEGIN CERTIFICATE/ {c++} c > 0 { print > "/usr/local/share/ca-certificates/agw-" c ".crt" }' && \
      update-ca-certificates && rm -rf /var/lib/apt/lists/*; \
    fi

ENV GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}
ENV REQUESTS_CA_BUNDLE=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}
ENV SSL_CERT_FILE=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}
ENV SSL_CERT_DIR=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs}
ENV AGENT_GATEWAY_ROOT_CERT_302034098528=${AGENT_GATEWAY_ROOT_CERTIFICATES:+/etc/ssl/certs/ca-certificates.crt}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the modular Python ADK & FastAPI application and sanitized schema templates
COPY app/ ./app/
COPY data/*.example.json ./data/

ENV PORT=8080
ENV AGENT_ROLE=travel-router
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${AIP_HTTP_PORT:-${PORT:-8080}}"]

