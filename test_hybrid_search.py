"""
Hybrid Search Demo: Vector Similarity + Keyword Matching

This script demonstrates the hybrid retrieval strategy for the RAG pipeline,
combining semantic vector search with keyword matching for comprehensive recall.
"""

from cassandra.cluster import Cluster
from sentence_transformers import SentenceTransformer
import re

# Load embedding model
print("Loading GTE-large embedding model...")
model = SentenceTransformer('thenlper/gte-large')
print("Model loaded!\n")

# Connect to Cassandra
cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()
session.set_keyspace('transcript_db')

# Get class info
print("=== Getting class info ===")
transcript_query = "SELECT class_name, professor, semester FROM transcripts WHERE status = 'success' LIMIT 1 ALLOW FILTERING;"
transcript_rows = list(session.execute(transcript_query))

if not transcript_rows:
    print("No successful transcripts found")
    cluster.shutdown()
    exit(1)

class_info = transcript_rows[0]
print(f"Searching in: {class_info.class_name} - {class_info.professor} ({class_info.semester})\n")

# The question
question = "What is the difference between OLAP and OLTP? Which one is column-oriented?"
print(f"Question: {question}\n")

# Extract keywords (simple regex for demo - in production, use NLP)
keywords = re.findall(r'\b[A-Z]{3,}\b', question)  # Finds OLAP, OLTP
print(f"Extracted keywords: {keywords}\n")

# === VECTOR SEARCH ===
print("=== Vector Similarity Search ===")
question_embedding = model.encode(question, normalize_embeddings=True).tolist()

vector_query = """
    SELECT chunk_index, chunk_text, token_count, lecture_timestamp, lecture_title, url
    FROM embeddings
    WHERE class_name = %s
      AND professor = %s
      AND semester = %s
    ORDER BY embedding ANN OF %s
    LIMIT 15
"""

vector_results = list(session.execute(vector_query, (
    class_info.class_name,
    class_info.professor,
    class_info.semester,
    question_embedding
)))

print(f"Found {len(vector_results)} chunks via vector search")
vector_ids = {(r.url, r.chunk_index) for r in vector_results}

# === KEYWORD SEARCH ===
print("\n=== Keyword Search ===")
keyword_query_str = " OR ".join(keywords)  # "OLAP OR OLTP"
print(f"Keyword query: {keyword_query_str}")

keyword_query = """
    SELECT chunk_index, chunk_text, token_count, lecture_timestamp, lecture_title, url
    FROM embeddings
    WHERE class_name = %s
      AND professor = %s
      AND semester = %s
      AND chunk_text : %s
    LIMIT 20
"""

keyword_results = list(session.execute(keyword_query, (
    class_info.class_name,
    class_info.professor,
    class_info.semester,
    keyword_query_str
)))

print(f"Found {len(keyword_results)} chunks via keyword search")
keyword_ids = {(r.url, r.chunk_index) for r in keyword_results}

# === HYBRID: MERGE AND DEDUPLICATE ===
print("\n=== Hybrid Results (Merged) ===")

# Combine results
all_results = {}
for r in vector_results:
    chunk_id = (r.url, r.chunk_index)
    all_results[chunk_id] = {
        'chunk': r,
        'sources': ['vector']
    }

for r in keyword_results:
    chunk_id = (r.url, r.chunk_index)
    if chunk_id in all_results:
        all_results[chunk_id]['sources'].append('keyword')
    else:
        all_results[chunk_id] = {
            'chunk': r,
            'sources': ['keyword']
        }

# Rank by source diversity (chunks from both searches ranked higher)
ranked_results = sorted(
    all_results.values(),
    key=lambda x: (len(x['sources']), x['chunk'].chunk_index),  # Prefer chunks found by both methods
    reverse=True
)

print(f"Total unique chunks: {len(ranked_results)}")
print(f"Chunks found by BOTH methods: {sum(1 for r in ranked_results if len(r['sources']) == 2)}")
print(f"Vector-only: {sum(1 for r in ranked_results if r['sources'] == ['vector'])}")
print(f"Keyword-only: {sum(1 for r in ranked_results if r['sources'] == ['keyword'])}")

# === WRITE TOP 10 TO FILE ===
output_file = "hybrid_search_results.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f"=== Hybrid Search Results ===\n")
    f.write(f"Question: {question}\n")
    f.write(f"Keywords: {', '.join(keywords)}\n")
    f.write(f"Class: {class_info.class_name} | Professor: {class_info.professor} | Semester: {class_info.semester}\n")
    f.write(f"\nTotal unique chunks: {len(ranked_results)}\n")
    f.write("=" * 80 + "\n\n")

    for idx, result in enumerate(ranked_results[:10], 1):
        chunk = result['chunk']
        sources_str = " + ".join(result['sources']).upper()

        f.write(f"[RANK #{idx}] [{sources_str}] Chunk {chunk.chunk_index} from {chunk.lecture_title}\n")
        f.write(f"URL: {chunk.url}\n")
        f.write(f"Timestamp: {chunk.lecture_timestamp}\n")
        f.write(f"Token count: {chunk.token_count}\n")
        f.write("-" * 80 + "\n")
        f.write(chunk.chunk_text)
        f.write("\n" + "=" * 80 + "\n\n")

print(f"\n✓ Wrote top 10 hybrid results to {output_file}")

# === ANALYSIS ===
print("\n=== Analysis ===")
top_10 = ranked_results[:10]
both_methods = [r for r in top_10 if len(r['sources']) == 2]
print(f"In top 10: {len(both_methods)} chunks found by BOTH methods")
print(f"This demonstrates the value of hybrid search - combining semantic similarity with exact keyword matching\n")

# Show preview
print("=== Top 3 Results Preview ===")
for idx, result in enumerate(ranked_results[:3], 1):
    chunk = result['chunk']
    sources_str = " + ".join(result['sources']).upper()

    # Get first sentence
    text = chunk.chunk_text
    first_sentence = text
    for delimiter in ['. ', '? ', '! ']:
        pos = text.find(delimiter)
        if pos != -1 and pos < len(first_sentence):
            first_sentence = text[:pos + 1]

    print(f"[#{idx}] [{sources_str}] {chunk.lecture_title} - Chunk {chunk.chunk_index}")
    print(f"  {first_sentence}")
    print()

cluster.shutdown()
print("Connection closed.")
