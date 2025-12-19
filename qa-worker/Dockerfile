FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY qa-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all qa-worker code (includes qa.py, qa_tools.py, qa_prompts.py, retrieval.py, worker.py)
COPY qa-worker/*.py .

CMD ["python", "worker.py"]
