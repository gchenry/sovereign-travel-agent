# Stateless Multi-Agent Container Image (Local Docker -> Google Cloud Run)
FROM python:3.11-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the modular Python ADK & FastAPI application and sanitized schema templates
COPY app/ ./app/
COPY data/*.example.json ./data/

ENV PORT=8080
ENV AGENT_ROLE=travel-router
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
