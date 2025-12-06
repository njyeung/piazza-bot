from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import os
import time
import sys

# Configuration from environment variables
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
KAFKA_TOPIC = 'transcript-events'
RETRY_DELAY = 5
MAX_RETRIES = 10

def wait_for_kafka():
    """Wait for Kafka broker to be ready with retry logic"""
    
    retries = 0
    while retries < MAX_RETRIES:
        try:
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

def create_topic():
    """Create Kafka topic, deleting it first if it already exists"""

    admin_client = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        request_timeout_ms=10000
    )

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
        print(f"Creating topic '{KAFKA_TOPIC}'...")
        admin_client.create_topics([topic])
        print(f"Topic '{KAFKA_TOPIC}' created successfully")

    except TopicAlreadyExistsError:
        print(f"Topic '{KAFKA_TOPIC}' already exists - deleting and recreating...")

        # Delete the existing topic
        admin_client.delete_topics([KAFKA_TOPIC])
        print(f"Deleted topic '{KAFKA_TOPIC}'")

        # Wait for deletion to complete
        time.sleep(3)

        # Recreate the topic
        print(f"Recreating topic '{KAFKA_TOPIC}'...")
        admin_client.create_topics([topic])
        print(f"Topic '{KAFKA_TOPIC}' recreated successfully")

    finally:
        admin_client.close()

def main():
    print("Starting Kafka initialization...")

    # Wait for Kafka to be ready
    wait_for_kafka()

    try:
        create_topic()
        print(f"\nKafka initialization complete!")

    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
