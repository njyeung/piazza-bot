"""
QA Worker - Processes jobs from Redis queue
Multiple instances can run in parallel (horizontally scaled)
Each worker maintains long-lived Cassandra session + embedding model
"""

import json
import os
import sys
import redis
from cassandra.cluster import Cluster
from sentence_transformers import SentenceTransformer

# Import QA pipeline (in same directory now)
from qa import run_qa_pipeline, save_answer_to_db

# Configuration
CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOSTS', 'cassandra').split(',')
KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'thenlper/gte-large')
LLM_MODEL = os.getenv('LLM_MODEL', 'qwen3:4b')

REDIS_QUEUE = 'qa-jobs-normal'


def connect_cassandra():
    """Connect to Cassandra and return session"""
    print(f"Connecting to Cassandra at {CASSANDRA_HOSTS}...")
    cluster = Cluster(CASSANDRA_HOSTS)
    session = cluster.connect(KEYSPACE)
    print("Connected to Cassandra!")
    return session


def connect_redis():
    """Connect to Redis and return client"""
    print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    client.ping()
    print("Connected to Redis!")
    return client


def main():
    """Main worker loop"""
    print("="*60)
    print("QA Worker Starting")
    print("="*60)

    # 1. Setup long-lived resources (ONE TIME)
    print("\nConnecting to services...")
    cassandra_session = connect_cassandra()
    redis_client = connect_redis()

    print(f"\nLoading embedding model ({EMBEDDING_MODEL})...")
    print("This may take 30-60 seconds...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    print("Embedding model loaded!")

    print("\n" + "="*60)
    print("QA Worker ready! Waiting for jobs...")
    print("="*60 + "\n")

    # 2. Process jobs from queue (INFINITE LOOP)
    job_count = 0

    while True:
        try:
            # Blocking pop from queue (waits up to 60s for job)
            result = redis_client.brpop(REDIS_QUEUE, timeout=60)

            if result is None:
                # Timeout, no jobs available
                continue

            # Parse job
            _, job_json = result  # brpop returns (queue_name, value)
            job = json.loads(job_json)

            job_count += 1
            print(f"\n[Job #{job_count}] Processing: {job['class_name']} post #{job['post_id']}")

            # 3. Run QA pipeline (reuses session and model)
            answer = run_qa_pipeline(
                session=cassandra_session,
                embedding_model=embedding_model,
                piazza_post=job['post_text'],
                class_name=job['class_name'],
                professor=job['professor'],
                semester=job['semester'],
                model=LLM_MODEL
            )

            # 4. Determine status
            if answer == "NO RESPONSE":
                status = "no_response"
            else:
                status = "success"

            # 5. Save to Cassandra
            save_answer_to_db(
                session=cassandra_session,
                class_name=job['class_name'],
                professor=job['professor'],
                semester=job['semester'],
                post_id=job['post_id'],
                piazza_post=job['post_text'],
                answer=answer,
                status=status
            )

            print(f"✓ Job complete (status: {status})")
            print("="*60)

        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except Exception as e:
            print(f"Error processing job: {e}")
            import traceback
            traceback.print_exc()
            print("Continuing to next job...")


if __name__ == '__main__':
    main()
