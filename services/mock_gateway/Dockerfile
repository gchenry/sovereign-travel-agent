FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mock_gateway/proxy.py ./proxy.py

EXPOSE 8095

CMD ["sh", "-c", "uvicorn proxy:app --host 0.0.0.0 --port ${PORT:-8095}"]
