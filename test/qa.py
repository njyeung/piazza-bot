import ollama
from sentence_transformers import SentenceTransformer
from retrieval import connect_db
from qa_tools import QATools
from qa_prompts import get_answerability_prompt, get_final_answer_prompt
import os
from datetime import datetime as dt

# Configuration
CASSANDRA_HOSTS = ['localhost']
KEYSPACE = 'transcript_db'
CLASS_NAME = 'CS544'
PROFESSOR = 'Tyler'
SEMESTER = 'FALL25'
MODEL = 'qwen3:4b'

# Test input - paste your Piazza post here and its ID
PIAZZA_POST_ID = 123  # Unique Piazza post ID number
PIAZZA_POST = """S23 Final Review Q4

Could someone explain how the answer here is A?"""


def save_answer_to_db(session, post_id, piazza_post, answer, status):
    """
    Save the generated answer to Cassandra

    Args:
        session: Cassandra session
        post_id: Piazza post ID
        piazza_post: The original question
        answer: The generated answer
        status: Status of the answer (e.g., 'success', 'not_answerable', 'no_response')
    """
    
    insert_query = """
    INSERT INTO piazza_answers (class_name, professor, semester, post_id, piazza_post, answer, status, created_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    session.execute(insert_query, (
        CLASS_NAME,
        PROFESSOR,
        SEMESTER,
        post_id,
        piazza_post,
        answer,
        status,
        dt.now()
    ))

    print(f"\n  Answer saved to database (post_id: {post_id}, status: {status})")


def check_answerability(piazza_post: str, model: str = MODEL) -> bool:
    """
    Check if Piazza post is answerable from lecture content

    Args:
        piazza_post: The student's question
        model: LLM model to use

    Returns:
        bool: True if answerable, False otherwise
    """
    prompt = get_answerability_prompt(piazza_post)

    response = ollama.chat(
        model=model,
        messages=[{'role': 'user', 'content': prompt}]
    )

    result = response['message']['content'].strip()
    return result == "ANSWERABLE"


def run_qa_pipeline(session, embedding_model, piazza_post: str) -> str:
    """
    Run the single-pass Q&A pipeline

    Pipeline stages:
    1. Check if post is answerable (early exit if not)
    2. Extract keywords using LLM
    3. Run both RAG and keyword search
    4. Deduplicate and expand chunks to clusters
    5. Check relevance of each cluster and generate summaries
    6. Generate final answer from relevant clusters

    Args:
        session: Cassandra session (reusable across requests)
        embedding_model: SentenceTransformer model (reusable across requests)
        piazza_post: The student's question

    Returns:
        str: Final answer or "NO RESPONSE" if no relevant information found
    """
    print("ANSWERABILITY CHECK")
    is_answerable = check_answerability(piazza_post)

    if not is_answerable:
        print("\n  Result: NOT_ANSWERABLE")
        print("\n  This post is not answerable from lecture content (administrative/logistics/policy question)")
        return "NO RESPONSE"

    print("\n  Result: ANSWERABLE")
    print("\n  Proceeding with retrieval pipeline...")

    # Initialize QATools
    qa_tools = QATools(session, embedding_model, piazza_post, CLASS_NAME, PROFESSOR, SEMESTER, MODEL, limit=5)

    # Extract keywords
    print("KEYWORD EXTRACTION")
    keywords = qa_tools.extract_keywords()

    # Retrieve chunks
    print("RETRIEVAL")
    rag_chunks, keyword_chunks = qa_tools.retrieve_chunks(keywords)

    # Deduplicate and expand to clusters
    print("DEDUPLICATION & EXPANSION")
    clusters = qa_tools.deduplicate_and_expand(rag_chunks, keyword_chunks)

    if not clusters:
        print("\n  No clusters found")
        return "NO RESPONSE"

    # Check relevance of clusters
    print("RELEVANCE CHECKING")
    relevant_clusters = qa_tools.check_cluster_relevance(clusters)

    if not relevant_clusters:
        print(f"\n{'='*60}")
        print("NO RELEVANT INFORMATION FOUND")
        print(f"{'='*60}")
        return "NO RESPONSE"

    # Generate final answer
    print("FINAL ANSWER GENERATION")
    print(f"  Using {len(relevant_clusters)} relevant clusters\n")

    context = QATools.format_context_for_answer(relevant_clusters)
    final_prompt = get_final_answer_prompt(context, piazza_post)

    final_response = ollama.chat(
        model=MODEL,
        messages=[{'role': 'user', 'content': final_prompt}]
    )

    final_answer = final_response['message']['content'].strip()
    return final_answer


def main():
    """Run the Q&A system on the test Piazza post and save to database"""

    print("Connecting to Cassandra...")
    session = connect_db(CASSANDRA_HOSTS, KEYSPACE)
    print("Connected!")

    print("Loading embedding model...")
    embedding_model = SentenceTransformer('thenlper/gte-large')
    print("Model loaded!\n")

    final_answer = run_qa_pipeline(session, embedding_model, PIAZZA_POST)

    print(f"\n{'='*60}")
    print("FINAL ANSWER")
    print(f"{'='*60}")
    print(final_answer)
    print(f"{'='*60}\n")

    # Save to database
    print("Saving answer to database...")
    if final_answer == "NO RESPONSE":
        save_answer_to_db(session, PIAZZA_POST_ID, PIAZZA_POST, final_answer, "no_response")
    else:
        save_answer_to_db(session, PIAZZA_POST_ID, PIAZZA_POST, final_answer, "success")


if __name__ == '__main__':
    main()
