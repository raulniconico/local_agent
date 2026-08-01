FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Provider keys and SERVER_API_KEY are injected at deploy time (ECS task
# definition / App Runner env vars, ideally sourced from AWS Secrets Manager
# or SSM Parameter Store) -- .env is excluded by .dockerignore, never baked
# into the image.
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
