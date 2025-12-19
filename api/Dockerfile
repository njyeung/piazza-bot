FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API server code
COPY api/server.py .

# Expose Flask port
EXPOSE 5000

CMD ["python", "-u", "server.py"]
