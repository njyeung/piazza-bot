from cassandra.cluster import Cluster
import pandas as pd
import os

cluster = Cluster(['localhost'], port=9042)
session = cluster.connect()
session.set_keyspace('transcript_db')

# Query first few rows from transcripts table
query = "SELECT * FROM transcripts LIMIT 5;"
rows = session.execute(query)

# Convert to pandas DataFrame
df = pd.DataFrame(list(rows))
print(df)

cluster.shutdown()
print("Connection closed.")