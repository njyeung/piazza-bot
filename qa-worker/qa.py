import os
from ollama import Client
from sentence_transformers import SentenceTransformer
from retrieval import connect_db
from qa_tools import QATools
from qa_prompts import get_answerability_prompt, get_final_answer_prompt
from datetime import datetime as dt

# Configure Ollama client to use LLM container
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
ollama_client = Client(host=OLLAMA_HOST)
MODEL = os.getenv('LLM_MODEL', 'qwen3:4b')


def save_answer_to_db(session, class_name, professor, semester, post_id, piazza_post, answer, status):
    """
    Save the generated answer to Cassandra

    Args:
        session: Cassandra session
        class_name: Course name (e.g., 'CS544')
        professor: Professor name (e.g., 'Tyler')
        semester: Semester (e.g., 'FALL25')
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
        class_name,
        professor,
        semester,
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

    response = ollama_client.chat(
        model=model,
        messages=[{'role': 'user', 'content': prompt}]
    )

    result = response['message']['content'].strip()
    return result == "ANSWERABLE"


def run_qa_pipeline(session, embedding_model, piazza_post: str, class_name: str, professor: str, semester: str, model: str = MODEL, limit: int = 5) -> str:
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
        class_name: Course name (e.g., 'CS544')
        professor: Professor name (e.g., 'Tyler')
        semester: Semester (e.g., 'FALL25')
        model: LLM model name (default: 'qwen3:4b')
        limit: Max results per search (default: 5)

    Returns:
        str: Final answer or "NO RESPONSE" if no relevant information found
    """
    print("ANSWERABILITY CHECK")
    is_answerable = check_answerability(piazza_post, model)

    if not is_answerable:
        print("\n  Result: NOT_ANSWERABLE")
        print("\n  This post is not answerable from lecture content (administrative/logistics/policy question)")
        return "NO RESPONSE"

    print("\n  Result: ANSWERABLE")
    print("\n  Proceeding with retrieval pipeline...")

    # Initialize QATools
    qa_tools = QATools(session, embedding_model, piazza_post, class_name, professor, semester, model, limit)

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

    print(context)
    
    final_prompt = get_final_answer_prompt(context, piazza_post)

    final_response = ollama_client.chat(
        model=model,
        messages=[{'role': 'user', 'content': final_prompt}],
        think=True
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

    final_answer = run_qa_pipeline(session, embedding_model, PIAZZA_POST, CLASS_NAME, PROFESSOR, SEMESTER)

    print(f"\n{'='*60}")
    print("FINAL ANSWER")
    print(f"{'='*60}")
    print(final_answer)
    print(f"{'='*60}\n")

    # Save to database
    print("Saving answer to database...")
    if final_answer == "NO RESPONSE":
        save_answer_to_db(session, CLASS_NAME, PROFESSOR, SEMESTER, PIAZZA_POST_ID, PIAZZA_POST, final_answer, "no_response")
    else:
        save_answer_to_db(session, CLASS_NAME, PROFESSOR, SEMESTER, PIAZZA_POST_ID, PIAZZA_POST, final_answer, "success")


