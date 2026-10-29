FROM python:3.11-slim

# One Dockerfile for the whole stack; the build selects the service code and
# the runtime keeps the same name available to the process.
ARG SERVICE_NAME=gateway
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    SERVICE_NAME=${SERVICE_NAME}

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY services/common ./common
COPY services/${SERVICE_NAME}/app.py ./app.py

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
