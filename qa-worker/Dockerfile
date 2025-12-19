FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY qa-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all qa-worker code
COPY qa-worker/*.py .

CMD ["python", "-u", "worker.py"]
