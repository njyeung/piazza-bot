FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy monitor code
COPY monitor.py .

# Command will be specified in docker-compose
CMD ["python", "monitor.py"]
