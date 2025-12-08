from cassandra.cluster import Cluster
import pandas as pd
from sentence_transformers import SentenceTransformer

# Load the same embedding model used by the processor
# Model: thenlper/gte-large (1024 dimensions)
print("Loading GTE-large embedding model...")
model = SentenceTransformer('thenlper/gte-large')
print("Model loaded!\n")

cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()
session.set_keyspace('transcript_db')

# Step 1: Get class info for query scope
print("=== Getting class info ===")
transcript_query = "SELECT class_name, professor, semester FROM transcripts WHERE status = 'success' LIMIT 1 ALLOW FILTERING;"
transcript_rows = list(session.execute(transcript_query))

if not transcript_rows:
    print("No successful transcripts found in database")
    cluster.shutdown()
    exit(1)

class_info = transcript_rows[0]
print(f"Searching in: {class_info.class_name} - {class_info.professor} ({class_info.semester})")
print()

# Step 2: Embed the question
question = "What is the difference between OLAP and OLTP? Which one should is column orientated and which one is row orientated?"
print(f"Question: {question}")
print("Embedding question...")
question_embedding = model.encode(question, normalize_embeddings=True).tolist()
print(f"Question embedding dimension: {len(question_embedding)}\n")

# Step 3: Vector similarity search (ANN query)
print("=== Searching for top 10 most relevant chunks ===")
search_query = """
    SELECT chunk_index, chunk_text, token_count, lecture_timestamp, lecture_title, url
    FROM embeddings
    WHERE class_name = %s
      AND professor = %s
      AND semester = %s
    ORDER BY embedding ANN OF %s
    LIMIT 20
"""

chunk_rows = list(session.execute(search_query, (
    class_info.class_name,
    class_info.professor,
    class_info.semester,
    question_embedding
)))

if not chunk_rows:
    print("No relevant chunks found")
else:
    print(f"Found {len(chunk_rows)} relevant chunks\n")

    # Step 4: Write top 10 chunks to file
    output_file = "rag_results.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"=== RAG Query Results ===\n")
        f.write(f"Question: {question}\n")
        f.write(f"Class: {class_info.class_name} | Professor: {class_info.professor} | Semester: {class_info.semester}\n")
        f.write(f"Top {len(chunk_rows)} most relevant chunks:\n")
        f.write("=" * 80 + "\n\n")

        for idx, chunk in enumerate(chunk_rows, 1):
            f.write(f"[RANK #{idx}] Chunk {chunk.chunk_index} from {chunk.lecture_title}\n")
            f.write(f"URL: {chunk.url}\n")
            f.write(f"Timestamp: {chunk.lecture_timestamp}\n")
            f.write(f"Token count: {chunk.token_count}\n")
            f.write("-" * 80 + "\n")
            f.write(chunk.chunk_text)
            f.write("\n" + "=" * 80 + "\n\n")

    print(f"✓ Wrote {len(chunk_rows)} relevant chunks to {output_file}")

    # Also print preview to console
    print("\n=== Top Results Preview ===")
    for idx, chunk in enumerate(chunk_rows[:3], 1):  # Show top 3
        # Get first sentence
        text = chunk.chunk_text
        first_sentence = text
        for delimiter in ['. ', '? ', '! ']:
            pos = text.find(delimiter)
            if pos != -1 and (pos < len(first_sentence) or len(first_sentence) == len(text)):
                first_sentence = text[:pos + 1]

        print(f"[#{idx}] {chunk.lecture_title} - Chunk {chunk.chunk_index} (@{chunk.lecture_timestamp})")
        print(f"  {first_sentence}")
        print()

cluster.shutdown()
print("Connection closed.")