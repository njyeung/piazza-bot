from cassandra.cluster import Cluster
import os
import time
import sys

# Configuration from environment variables
CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOSTS', 'cassandra-1').split(',')
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')
RETRY_DELAY = 5

def wait_for_cassandra():
    """Wait for Cassandra cluster to be ready with retry logic"""
    while True:
        try:
            print(f"Connecting to Cassandra at {CASSANDRA_HOSTS}...")
            cluster = Cluster(CASSANDRA_HOSTS)
            session = cluster.connect()
            print("Successfully connected to Cassandra!")
            return cluster, session
        except Exception as e:
            time.sleep(RETRY_DELAY)

def create_keyspace(session):
    """Create keyspace with replication factor 3"""
    print(f"\nCreating keyspace: {CASSANDRA_KEYSPACE}")

    create_keyspace_query = f"""
    CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
    WITH replication = {{
        'class': 'SimpleStrategy',
        'replication_factor': 3
    }}
    """

    session.execute(create_keyspace_query)
    print(f"Keyspace '{CASSANDRA_KEYSPACE}' created successfully")

def create_transcript_table(session):
    """Create transcripts table"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.transcripts")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_transcript_table_query = """
    CREATE TABLE IF NOT EXISTS transcripts (
        class_name text,
        professor text,
        semester text,
        url text,
        lecture_number int,
        lecture_title text,
        transcript_text text,
        downloaded_at timestamp,
        status text,
        PRIMARY KEY ((class_name, professor, semester), url)
    )
    """

    session.execute(create_transcript_table_query)
    print("Table 'transcripts' created successfully")

def create_parsers_table(session):
    """Create parsers table for storing parser code"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.parsers")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_table_query = """
    CREATE TABLE IF NOT EXISTS parsers (
        parser_name text PRIMARY KEY,
        code_text text
    )
    """

    session.execute(create_table_query)
    print("Table 'parsers' created successfully")

def main():
    """Main initialization function"""

    # Connect to Cassandra
    cluster, session = wait_for_cassandra()

    try:
        # Create keyspace
        create_keyspace(session)

        # Create tables
        create_transcript_table(session)
        create_parsers_table(session)

        print("Database initialization completed successfully")

    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)
    finally:
        cluster.shutdown()
        print("Connection closed.")

if __name__ == "__main__":
    main()
