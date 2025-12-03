from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import os
import time
import sys

# Configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'transcript-events')
RETRY_DELAY = 5
MAX_RETRIES = 30

def wait_for_kafka():
    """Wait for Kafka broker to be ready with retry logic"""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            print(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
            admin_client = KafkaAdminClient(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                request_timeout_ms=5000
            )
            admin_client.close()
            print("Successfully connected to Kafka!")
            return admin_client
        except Exception as e:
            retries += 1
            print(f"Connection attempt {retries}/{MAX_RETRIES} failed. Retrying in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    print("Failed to connect to Kafka after maximum retries")
    sys.exit(1)

def create_topic(admin_client):
    """Create Kafka topic for transcript events

    Topic design:
    - Partitioned by (class_name, professor, semester) composite key
    - Each partition can process a batch of transcripts independently
    - Message format: JSON with row identifiers for Cassandra query:
      {
        "class_name": "CS101",
        "professor": "Dr. Smith",
        "semester": "Fall2024",
        "url": "...",
        "timestamp": "..."
      }
    """
    print(f"\nCreating topic: {KAFKA_TOPIC}")

    topic = NewTopic(
        name=KAFKA_TOPIC,
        num_partitions=3,
        replication_factor=1,
        topic_configs={
            'retention.ms': '604800000',
            'cleanup.policy': 'delete'
        }
    )

    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            request_timeout_ms=5000
        )

        result = admin_client.create_topics([topic], validate_only=False)

        # Wait for topic creation to complete
        for topic_name, future in result.items():
            try:
                future.result()
                print(f"Topic '{topic_name}' created successfully")
            except TopicAlreadyExistsError:
                print(f"Topic '{topic_name}' already exists")

        admin_client.close()

    except Exception as e:
        print(f"Error creating topic: {e}")
        sys.exit(1)

def main():
    """Main initialization function"""
    print("Starting Kafka initialization...")

    # Wait for Kafka to be ready
    admin_client = wait_for_kafka()

    try:
        # Create topic
        create_topic(admin_client)
        
        print(f"Topic '{KAFKA_TOPIC}' is ready for use")

    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
