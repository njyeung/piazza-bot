"""
Usage:
    python manage.py apply    # Sync parsers/ directory to Cassandra (idempotent)
    python manage.py list     # List parsers in Cassandra
"""

import sys
import os
from pathlib import Path
from cassandra.cluster import Cluster

CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'localhost')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', 9042))
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'transcript_db')
PARSERS_DIR = Path(__file__).parent / 'parsers'


def get_cassandra_session():
    """Connect to Cassandra and return session"""
    try:
        print(f"Connecting to Cassandra at {CASSANDRA_HOST}:{CASSANDRA_PORT}...")
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        session = cluster.connect()
        session.set_keyspace(CASSANDRA_KEYSPACE)
        print("Connected successfully!\n")
        return cluster, session
    except Exception as e:
        print(f"Error connecting to Cassandra: {e}")
        print("Make sure Cassandra is running and accessible at localhost:9042")
        sys.exit(1)


def read_parser_file(file_path):
    """
    Read a parser file and return its name and contents.

    Returns: (parser_name, code_text)
    """
    parser_name = file_path.stem

    # Read the code
    with open(file_path, 'r') as f:
        code_text = f.read()

    return parser_name, code_text


def apply_command(session):
    """Apply local parsers/ directory state to Cassandra (adds, updates, deletes)"""
    print(f"Scanning {PARSERS_DIR} for parser files...\n")

    if not PARSERS_DIR.exists():
        print(f"Error: Parsers directory not found at {PARSERS_DIR}")
        return

    # Find all .py files
    parser_files = [f for f in PARSERS_DIR.glob("*.py")]

    local_parser_names = {f.stem for f in parser_files}
    print(f"Found {len(parser_files)} parser(s) in local directory\n")

    # Get existing parsers from Cassandra
    rows = session.execute("SELECT parser_name FROM parsers")
    cassandra_parser_names = {row.parser_name for row in rows}
    print(f"Found {len(cassandra_parser_names)} parser(s) in Cassandra\n")

    # Determine what needs to be added/updated vs deleted
    to_apply = local_parser_names
    to_delete = cassandra_parser_names - local_parser_names

    # Apply parsers (add/update)
    apply_stmt = session.prepare("""
        INSERT INTO parsers (parser_name, code_text)
        VALUES (?, ?)
    """)

    applied_count = 0
    if to_apply:
        print("Applying parsers:")
        for parser_file in parser_files:
            try:
                parser_name, code_text = read_parser_file(parser_file)

                session.execute(apply_stmt, (
                    parser_name,
                    code_text
                ))

                print(f"{parser_name}")
                applied_count += 1

            except Exception as e:
                print(f"Failed to apply {parser_file.name}: {e}")
        print()

    # Delete parsers that no longer exist locally
    deleted_count = 0
    if to_delete:
        print("Removing parsers no longer in local directory:")
        delete_stmt = session.prepare("DELETE FROM parsers WHERE parser_name = ?")
        for parser_name in to_delete:
            try:
                session.execute(delete_stmt, (parser_name,))
                print(f"Deleted: {parser_name}")
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete {parser_name}: {e}")
        print()

    # Summary
    print(f"Summary: {applied_count} applied, {deleted_count} deleted")
    print(f"Cassandra now has {len(local_parser_names)} parser(s) (synced with local directory)")


def list_command(session):
    """List all parsers stored in Cassandra"""
    print("Parsers in Cassandra:\n")

    rows = session.execute("SELECT parser_name FROM parsers")

    parsers = list(rows)
    if not parsers:
        print("No parsers found.")
        return

    for row in parsers:
        print(f"  - {row.parser_name}")

    print(f"\nTotal: {len(parsers)} parser(s)")


def print_usage():
    """Print usage information"""
    print(__doc__)
    print("\nAvailable commands:")
    print("  apply    Sync parsers/ directory to Cassandra (adds/updates/removes)")
    print("  list     List all parsers in Cassandra")
    print("\nExamples:")
    print("  python manage.py apply")
    print("  python manage.py list")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    if command == 'apply':
        cluster, session = get_cassandra_session()
        try:
            apply_command(session)
        finally:
            cluster.shutdown()

    elif command == 'list':
        cluster, session = get_cassandra_session()
        try:
            list_command(session)
        finally:
            cluster.shutdown()

    else:
        print(f"Unknown command: {command}\n")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
