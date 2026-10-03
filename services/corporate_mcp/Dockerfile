FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/corporate_mcp/server.py ./server.py
COPY data/*.example.json ./data/

EXPOSE 8090

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8090}"]
