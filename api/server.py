"""Simple API server to query Piazza answers from Cassandra"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from cassandra.cluster import Cluster

app = Flask(__name__)
CORS(app)  # Enable CORS for Chrome extension

# Cassandra configuration
import os
CASSANDRA_HOSTS = os.getenv('CASSANDRA_HOSTS', 'localhost').split(',')
KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')

# Initialize Cassandra connection
cluster = Cluster(CASSANDRA_HOSTS)
session = cluster.connect(KEYSPACE)

print("Connected to Cassandra")

@app.route('/answer', methods=['GET'])
def get_answer():
    """
    Get answer for a Piazza post

    Query parameters:
    - network_id: Piazza network ID (e.g., "merk8zm4in1ib")
    - post_id: Piazza post ID (e.g., 940)

    Returns:
    - answer: The generated answer text
    - status: success/no_response/not_found
    """
    network_id = request.args.get('network_id')
    post_id = request.args.get('post_id')

    if not network_id or not post_id:
        return jsonify({"error": "Missing network_id or post_id"}), 400

    try:
        post_id = int(post_id)
    except ValueError:
        return jsonify({"error": "post_id must be an integer"}), 400

    # Step 1: Lookup course info from network_id
    config_query = """
        SELECT class_name, professor, semester
        FROM piazza_config
        WHERE network_id = %s
    """
    config_result = session.execute(config_query, [network_id])
    config_row = config_result.one()

    if not config_row:
        return jsonify({
            "error": "Network ID not found",
            "network_id": network_id
        }), 404

    class_name = config_row.class_name
    professor = config_row.professor
    semester = config_row.semester

    # Step 2: Query answer from piazza_answers
    answer_query = """
        SELECT answer, status, created_at
        FROM piazza_answers
        WHERE class_name = %s AND professor = %s AND semester = %s AND post_id = %s
    """
    answer_result = session.execute(answer_query, [class_name, professor, semester, post_id])
    answer_row = answer_result.one()

    if not answer_row:
        return jsonify({
            "status": "not_found",
            "message": "No answer found for this post"
        }), 404

    # Return the answer
    return jsonify({
        "answer": answer_row.answer,
        "status": answer_row.status,
        "created_at": answer_row.created_at.isoformat() if answer_row.created_at else None,
        "course": {
            "class_name": class_name,
            "professor": professor,
            "semester": semester
        }
    })


if __name__ == '__main__':
    print("Starting API server on http://localhost:5000")
    print("Endpoints:")
    print("  GET /health")
    print("  GET /answer?network_id=merk8zm4in1ib&post_id=940")
    app.run(host='0.0.0.0', port=5000, debug=True)
