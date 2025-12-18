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

    # fetch.py has W=1, processor Go has R=3
    # web scrapers get high throughput, processors are slower anyways

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

def create_embeddings_table(session):
    """Create embeddings table for storing chunk embeddings with vector search"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.embeddings")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_table_query = """
    CREATE TABLE IF NOT EXISTS embeddings (
        class_name text,
        professor text,
        semester text,
        url text,
        chunk_index int,
        chunk_text text,
        embedding VECTOR<FLOAT, 1024>,
        token_count int,
        lecture_title text,
        lecture_timestamp text,
        created_at timestamp,
        PRIMARY KEY ((class_name, professor, semester), url, chunk_index)
    )
    """

    session.execute(create_table_query)
    print("Table 'embeddings' created successfully")

    # Create ANN index for vector search
    embedding_index_query = """
    CREATE INDEX IF NOT EXISTS embedding_idx
    ON embeddings(embedding)
    USING 'SAI'
    """
    session.execute(embedding_index_query)
    print("Embedding index index 'embedding_idx' created successfully")

def create_inverted_index_table(session):
    """Create inverted index table for keyword search"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.keywords")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_table_query = """
    CREATE TABLE IF NOT EXISTS keywords (
        term text,
        class_name text,
        professor text,
        semester text,
        url text,
        chunk_index int,
        PRIMARY KEY ((term), class_name, professor, semester, url, chunk_index)
    )
    """

    session.execute(create_table_query)
    print("Table 'keywords' created successfully")

def create_piazza_answers_table(session):
    """Create piazza_answers table for storing generated answers"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.piazza_answers")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_table_query = """
    CREATE TABLE IF NOT EXISTS piazza_answers (
        class_name text,
        professor text,
        semester text,
        post_id int,
        piazza_post text,
        answer text,
        status text,
        created_at timestamp,
        PRIMARY KEY ((class_name, professor, semester), post_id)
    )
    """

    session.execute(create_table_query)
    print("Table 'piazza_answers' created successfully")

def create_piazza_config_table(session):
    """Create piazza_config table for mapping network IDs to courses"""
    print(f"\nCreating table: {CASSANDRA_KEYSPACE}.piazza_config")

    session.set_keyspace(CASSANDRA_KEYSPACE)

    create_table_query = """
    CREATE TABLE IF NOT EXISTS piazza_config (
        network_id text PRIMARY KEY,
        class_name text,
        professor text,
        semester text,
        email text,
        password text
    )
    """

    session.execute(create_table_query)
    print("Table 'piazza_config' created successfully")

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
        create_embeddings_table(session)
        create_inverted_index_table(session)
        create_piazza_answers_table(session)
        create_piazza_config_table(session)

        print("\nDatabase initialization completed successfully")

    except Exception as e:
        print(f"Error during initialization: {e}")
        sys.exit(1)
    finally:
        cluster.shutdown()
        print("Connection closed.")

if __name__ == "__main__":
    main()
