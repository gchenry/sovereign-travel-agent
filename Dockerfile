# Stateless Multi-Agent Container Image (Local Docker -> Google Cloud Run)
FROM python:3.11-slim

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the modular Python ADK & FastAPI application
COPY app/ ./app/

ENV PORT=8080
ENV AGENT_ROLE=travel-router
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
