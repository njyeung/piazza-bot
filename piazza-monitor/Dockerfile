FROM python:3.11

WORKDIR /app

# Install vim and other debugging tools
RUN apt-get update && apt-get install -y \
    vim \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY piazza-monitor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy monitor code
COPY piazza-monitor/monitor.py .

CMD ["python", "-u", "monitor.py"]
