FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATA_PATH=/app/data/churn.csv

WORKDIR /app
COPY services/frontend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services /app/services
COPY data/churn.csv /app/data/churn.csv

EXPOSE 8080
CMD ["uvicorn", "services.frontend.app:app", "--host", "0.0.0.0", "--port", "8080"]
