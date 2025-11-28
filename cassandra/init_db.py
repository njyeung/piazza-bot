from cassandra.cluster import Cluster
import os
import time
import sys

# Configuration from environment variables
CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOSTS', 'cassandra-1').split(',')
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')
MAX_RETRIES = 30
RETRY_DELAY = 5

def wait_for_cassandra():
    """Wait for Cassandra cluster to be ready with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            print(f"[Attempt {attempt + 1}/{MAX_RETRIES}] Connecting to Cassandra at {CASSANDRA_HOSTS}...")
            cluster = Cluster(CASSANDRA_HOSTS)
            session = cluster.connect()
            print("Successfully connected to Cassandra!")
            return cluster, session
        except Exception as e:
            print(f"Connection failed: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                print("Max retries reached. Exiting.")
                sys.exit(1)

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

def create_table(session):
    """Create transcripts table"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.transcripts")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_table_query = """
    CREATE TABLE IF NOT EXISTS transcripts (
        url text PRIMARY KEY,
        lecture_title text,
        transcript_text text,
        file_path text,
        downloaded_at timestamp,
        status text
    )
    """

    session.execute(create_table_query)
    print("Table 'transcripts' created successfully")

def describe_table(session):
    """Describe the transcripts table to verify schema"""
    print(f"\nDescribing table: {CASSANDRA_KEYSPACE}.transcripts")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    # Get table metadata
    cluster_metadata = session.cluster.metadata
    keyspace_metadata = cluster_metadata.keyspaces[CASSANDRA_KEYSPACE]
    table_metadata = keyspace_metadata.tables['transcripts']

    print("\n=== Table Schema ===")
    print(f"Table: {table_metadata.name}")
    print(f"Keyspace: {CASSANDRA_KEYSPACE}")
    print("\nColumns:")
    for column_name, column in table_metadata.columns.items():
        is_pk = "(PRIMARY KEY)" if column_name in [c.name for c in table_metadata.primary_key] else ""
        print(f"  - {column_name}: {column.cql_type} {is_pk}")

    print("\nPrimary Key:")
    for pk_column in table_metadata.primary_key:
        print(f"  - {pk_column.name}")

    print("\n=== Schema verification complete ===\n")

def main():
    """Main initialization function"""
    print("=== Cassandra Database Initialization ===\n")

    # Connect to Cassandra
    cluster, session = wait_for_cassandra()

    try:
        # Create keyspace
        create_keyspace(session)

        # Create table
        create_table(session)

        # Describe table to verify
        describe_table(session)

        print("Database initialization completed successfully!")

    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)
    finally:
        cluster.shutdown()
        print("Connection closed.")

if __name__ == "__main__":
    main()
