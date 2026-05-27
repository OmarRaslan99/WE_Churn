FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY services/preprocessing/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services /app/services

EXPOSE 8001
CMD ["uvicorn", "services.preprocessing.app:app", "--host", "0.0.0.0", "--port", "8001"]