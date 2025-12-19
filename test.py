from cassandra.cluster import Cluster
import pandas as pd
import os
from collections import defaultdict

cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()
session.set_keyspace('transcript_db')

query = """SELECT * FROM piazza_answers"""
rows = session.execute(query)

for row in rows:
    print(row)

# chunk_scores = defaultdict(int)
# for row in rows:
#     key = (row.class_name, row.professor, row.semester, row.url, row.chunk_index)
#     chunk_scores[key] += 1

# print(chunk_scores)

# sorted_keys = sorted(chunk_scores.keys(), key=lambda k: chunk_scores[k], reverse=True)[:20]

# results = []
# for class_name, professor, semester, url, chunk_index in sorted_keys:
#     rows = session.execute("""
#         SELECT *
#         FROM embeddings
#         WHERE class_name = %s AND professor = %s AND semester = %s AND url = %s AND chunk_index = %s
#     """, (class_name, professor, semester, url, chunk_index))
#     results.append(rows[0])

# df = pd.DataFrame(results)
# df.to_csv("test.csv", index=False)


cluster.shutdown()