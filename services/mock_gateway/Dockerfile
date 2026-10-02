FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mock_gateway/proxy.py ./proxy.py

ENV PORT=8095
EXPOSE 8095

CMD ["uvicorn", "proxy:app", "--host", "0.0.0.0", "--port", "8095"]
