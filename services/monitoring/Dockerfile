FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY services/monitoring/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services /app/services

EXPOSE 8002
CMD ["uvicorn", "services.monitoring.app:app", "--host", "0.0.0.0", "--port", "8002"]