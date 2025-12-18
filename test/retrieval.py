"""Cassandra retrieval functions"""
from cassandra.cluster import Cluster
from sentence_transformers import SentenceTransformer

def connect_db(hosts, keyspace):
    cluster = Cluster(hosts)
    session = cluster.connect(keyspace)
    return session

def vector_search(session, embedding_model, query, class_name, professor, semester, limit=5):
    embedding = embedding_model.encode(query, normalize_embeddings=True).tolist()
    results = session.execute("""
        SELECT url, chunk_index, chunk_text, lecture_title, lecture_timestamp
        FROM embeddings
        WHERE class_name = %s AND professor = %s AND semester = %s
        ORDER BY embedding ANN OF %s
        LIMIT %s
    """, (class_name, professor, semester, embedding, limit))
    return [dict(row._asdict()) for row in results]

def keyword_search(session, keywords, class_name, professor, semester, limit=5):
    # Use inverted index to get chunk pointers, score by keyword matches
    chunk_scores = {}  # (url, chunk_index) -> score

    for keyword in keywords:
        term_lower = keyword.lower()
        results = session.execute("""
            SELECT url, chunk_index
            FROM keywords
            WHERE term = %s AND class_name = %s AND professor = %s AND semester = %s
        """, (term_lower, class_name, professor, semester))

        for row in results:
            key = (row.url, row.chunk_index)
            chunk_scores[key] = chunk_scores.get(key, 0) + 1

    # Sort by score and get top results
    sorted_keys = sorted(chunk_scores.keys(), key=lambda k: chunk_scores[k], reverse=True)[:limit]

    # Fetch full chunk data from embeddings table
    chunks = []
    for url, chunk_index in sorted_keys:
        result = session.execute("""
            SELECT url, chunk_index, chunk_text, lecture_title, lecture_timestamp
            FROM embeddings
            WHERE class_name = %s AND professor = %s AND semester = %s AND url = %s AND chunk_index = %s
        """, (class_name, professor, semester, url, chunk_index))
        row = result.one()
        if row:
            chunks.append(dict(row._asdict()))

    return chunks

def expand_chunks(session, chunks, class_name, professor, semester):
    clusters = []
    for chunk in chunks:
        cluster_chunks = []
        for offset in [-1, 0, 1]:
            idx = chunk['chunk_index'] + offset
            if idx < 0:
                continue
            result = session.execute("""
                SELECT url, chunk_text, lecture_title, lecture_timestamp
                FROM embeddings
                WHERE class_name = %s AND professor = %s AND semester = %s
                  AND url = %s AND chunk_index = %s
            """, (class_name, professor, semester, chunk['url'], idx))
            row = result.one()
            if row:
                cluster_chunks.append(dict(row._asdict()))
        if cluster_chunks:
            clusters.append({
                'text': '\n\n'.join([c['chunk_text'] for c in cluster_chunks]),
                'metadata': cluster_chunks[0]
            })
    return clusters
