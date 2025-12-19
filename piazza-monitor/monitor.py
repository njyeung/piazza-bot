"""
Piazza Monitor - Polls Piazza for new posts and queues them for processing
Single instance, polls all courses from piazza_config table
"""

import time
import json
import os
from piazza_api import Piazza
from cassandra.cluster import Cluster
import redis
from bs4 import BeautifulSoup
from datetime import datetime

# Configuration
CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOSTS', 'cassandra').split(',')
KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '600'))  # 10 minutes default
MIN_AGE_SECONDS = int(os.getenv('MIN_AGE_SECONDS', '600'))  # 10 minutes default - wait for lectures to process

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


def fetch_courses_from_cassandra(session):
    """
    Query: SELECT * FROM piazza_config
    Only returns courses that were created at least MIN_AGE_SECONDS ago
    Returns: List of dicts with {network_id, class_name, professor, semester, email, password, created_at}
    """
    query = "SELECT * FROM piazza_config"
    rows = session.execute(query)

    courses = []
    now = datetime.now()

    for row in rows:
        # Check if created_at exists and is old enough
        if row.created_at:
            age_seconds = (now - row.created_at).total_seconds()
            if age_seconds < MIN_AGE_SECONDS:
                print(f"  Skipping {row.class_name} - created {int(age_seconds/60)} min ago (waiting {int(MIN_AGE_SECONDS/60)} min for lectures to process)")
                continue

        courses.append({
            'network_id': row.network_id,
            'class_name': row.class_name,
            'professor': row.professor,
            'semester': row.semester,
            'email': row.email,
            'password': row.password,
            'created_at': row.created_at
        })

    return courses


def get_last_processed_post(session, network_id):
    """
    Get last processed post ID for a course
    Returns: int (0 if never processed)
    """
    query = "SELECT last_processed_post_id FROM piazza_state WHERE network_id = %s"
    result = session.execute(query, [network_id])
    row = result.one()
    return row.last_processed_post_id if row else 0


def update_last_processed_post(session, network_id, post_id):
    """Update last processed post ID for a course"""
    query = """
        INSERT INTO piazza_state (network_id, last_processed_post_id, last_poll_time, updated_at)
        VALUES (%s, %s, %s, %s)
    """
    now = datetime.now()
    session.execute(query, [network_id, post_id, now, now])


def is_already_answered(session, class_name, professor, semester, post_id):
    """
    Check if post already has an answer in piazza_answers table
    Returns: True if exists, False otherwise
    """
    query = """
        SELECT post_id FROM piazza_answers
        WHERE class_name = %s AND professor = %s AND semester = %s AND post_id = %s
    """
    result = session.execute(query, [class_name, professor, semester, post_id])
    return result.one() is not None


def extract_post_content(post):
    """
    Combine subject + body into single text
    Handle HTML stripping if needed
    """
    try:
        # Piazza API returns posts with 'history' array
        history = post.get('history', [{}])
        if not history:
            return ""

        latest = history[0]
        subject = latest.get('subject', '')
        content = latest.get('content', '')

        # Strip HTML
        subject_text = BeautifulSoup(subject, 'html.parser').get_text() if subject else ''
        content_text = BeautifulSoup(content, 'html.parser').get_text() if content else ''

        return f"{subject_text}\n\n{content_text}".strip()
    except Exception as e:
        print(f"  Error extracting post content: {e}")
        return ""


def process_course(course, cassandra_session, redis_client):
    """
    For a single course:
    1. Login to Piazza
    2. Fetch posts newer than last_processed_post_id
    3. Check if already answered
    4. If not answered, push to Redis queue
    """
    network_id = course['network_id']
    class_name = course['class_name']

    print(f"\nProcessing {class_name} ({network_id})")

    try:
        # Get last processed post ID
        last_post_id = get_last_processed_post(cassandra_session, network_id)
        print(f"  Last processed post: {last_post_id}")

        # Login to Piazza
        piazza = Piazza()
        piazza.user_login(email=course['email'], password=course['password'])
        network = piazza.network(network_id)

        # Fetch recent posts (limit to 100)
        # Note: Piazza API doesn't have a "since" filter, so we fetch recent and filter
        print(f"  Fetching recent posts...")
        feed = network.get_feed(limit=100, offset=0)
        post_summaries = feed.get('feed', [])
        print(f"  Found {len(post_summaries)} total posts in feed")

        # Filter for posts newer than last_processed_post_id
        new_post_ids = []
        max_post_id = last_post_id

        for post_summary in post_summaries:
            post_id = int(post_summary.get('nr', 0))
            if post_id > last_post_id:
                new_post_ids.append(post_id)
                max_post_id = max(max_post_id, post_id)

        print(f"  Found {len(new_post_ids)} new posts (IDs > {last_post_id})")

        # Process new posts - fetch FULL post content
        queued_count = 0
        for post_id in new_post_ids:
            # Check if already answered
            if is_already_answered(cassandra_session, course['class_name'], course['professor'], course['semester'], post_id):
                print(f"    Post {post_id}: Already answered, skipping")
                continue

            # Fetch FULL post
            try:
                full_post = network.get_post(post_id)
            except Exception as e:
                print(f"    Post {post_id}: Error fetching full post: {e}")
                continue

            # Extract post content from full_post
            post_text = extract_post_content(full_post)
            if not post_text:
                print(f"    Post {post_id}: Empty content, skipping")
                continue

            # Queue to Redis
            job = {
                'class_name': course['class_name'],
                'professor': course['professor'],
                'semester': course['semester'],
                'post_id': post_id,
                'post_text': post_text
            }

            redis_client.lpush(REDIS_QUEUE, json.dumps(job))
            queued_count += 1
            print(f"    Post {post_id}: Queued for processing")

        print(f"  Queued {queued_count} posts")

        # Update last processed post ID
        if max_post_id > last_post_id:
            update_last_processed_post(cassandra_session, network_id, max_post_id)
            print(f"  Updated last processed post ID to {max_post_id}")

    except Exception as e:
        print(f"  Error processing course {class_name}: {e}")


def main():
    """Main polling loop"""
    print("="*60)
    print("Piazza Monitor Starting")
    print(f"Poll interval: {POLL_INTERVAL} seconds")
    print("="*60)

    # Setup connections (long-lived)
    cassandra_session = connect_cassandra()
    redis_client = connect_redis()

    print("\nMonitor ready!\n")

    while True:
        try:
            print(f"\n[{datetime.now()}] Starting poll cycle...")

            # Fetch all courses from piazza_config
            courses = fetch_courses_from_cassandra(cassandra_session)
            print(f"Monitoring {len(courses)} course(s)")

            if not courses:
                print("No courses configured in piazza_config table")

            # Process each course
            for course in courses:
                process_course(course, cassandra_session, redis_client)

            # Sleep until next poll cycle
            print(f"\nPoll cycle complete. Sleeping for {POLL_INTERVAL} seconds...")
            print("="*60)
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except Exception as e:
            print(f"Error in monitor loop: {e}")
            print("Retrying in 60 seconds...")
            time.sleep(60)


if __name__ == '__main__':
    main()
