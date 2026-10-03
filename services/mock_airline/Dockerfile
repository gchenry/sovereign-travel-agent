FROM python:3.11-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/mock_airline/app.py ./app.py

EXPOSE 8091

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8091}"]
