#!/usr/bin/env python3
"""
Embedding service that runs as a long-lived process.
Reads one line of text per request (sentence or chunk), outputs embedding as JSON.
"""

import sys
import json
from sentence_transformers import SentenceTransformer

try:
    model = SentenceTransformer('thenlper/gte-large')

    # Process lines from stdin in a loop
    for line in sys.stdin:
        line = line.strip()

        if not line:
            continue

        try:
            # Each line is a single text string (sentence or chunk)
            embedding = model.encode(line, convert_to_numpy=True)
            result = embedding.tolist()
            print(json.dumps(result))
            sys.stdout.flush()
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr, flush=True)
            sys.exit(1)

except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
