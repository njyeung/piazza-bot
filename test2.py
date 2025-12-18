"""Simple test script for embedding and KNN search in Cassandra"""
from sentence_transformers import SentenceTransformer
from cassandra.cluster import Cluster

# Configuration
CASSANDRA_HOSTS = ['localhost']
KEYSPACE = 'transcript_db'
CLASS_NAME = 'CS544'
PROFESSOR = 'Tyler'
SEMESTER = 'FALL25'
EMBEDDING_MODEL = 'thenlper/gte-large'

# Test query
TEST_QUERY = "why is Broadcast Hash Join most beneficial when one table is small and the other is large? Why wouldn't it help when both tables are small?"

def main():
    """Run a simple KNN search test"""

    print(f"Query: {TEST_QUERY}\n")
    print("=" * 80)

    # Load embedding model
    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    # Generate embedding for query
    print("Generating embedding for query...")
    query_embedding = model.encode(TEST_QUERY, normalize_embeddings=True).tolist()
    print(f"Embedding dimension: {len(query_embedding)}")

    # Connect to Cassandra
    print("\nConnecting to Cassandra...")
    cluster = Cluster(CASSANDRA_HOSTS)
    session = cluster.connect(KEYSPACE)
    print("Connected!")

    # Perform KNN search
    print(f"\nSearching for top 5 nearest neighbors...")
    print("=" * 80)

    query = """
        SELECT url, chunk_index, chunk_text, lecture_title, lecture_timestamp
        FROM embeddings
        WHERE class_name = %s AND professor = %s AND semester = %s
        ORDER BY embedding ANN OF %s
        LIMIT 5
    """

    results = session.execute(query, (CLASS_NAME, PROFESSOR, SEMESTER, query_embedding))

    # Display results
    for i, row in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"  Lecture: {row.lecture_title}")
        print(f"  Timestamp: {row.lecture_timestamp}")
        print(f"  URL: {row.url}")
        print(f"  Chunk Index: {row.chunk_index}")
        print(f"  Text Preview: {row.chunk_text}...")
        print("-" * 80)

    # Cleanup
    cluster.shutdown()
    print("\nDone!")

if __name__ == '__main__':
    main()
