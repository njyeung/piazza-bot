"""Simplified retrieval orchestrator for single-pass Q&A system"""
import ollama
from retrieval import vector_search, keyword_search, expand_chunks
from qa_prompts import get_relevance_prompt, get_keyword_extraction_prompt


class QATools:
    """Orchestrates the Q&A pipeline with stateful configuration"""

    def __init__(self, session, embedding_model, piazza_post, class_name, professor, semester, model='qwen3:4b', limit=5):
        """
        Initialize QA tools with configuration

        Args:
            session: Cassandra session
            embedding_model: SentenceTransformer model
            piazza_post: The student's question
            class_name: Course name (e.g., 'CS544')
            professor: Professor name
            semester: Semester (e.g., 'FALL25')
            model: LLM model name for keyword extraction and relevance checking
            limit: Max results per search type
        """
        self.session = session
        self.embedding_model = embedding_model
        self.piazza_post = piazza_post
        self.class_name = class_name
        self.professor = professor
        self.semester = semester
        self.model = model
        self.limit = limit

    def extract_keywords(self) -> list:
        """
        Extract keywords from Piazza post using LLM

        Returns:
            list: List of keyword strings
        """
        prompt = get_keyword_extraction_prompt(self.piazza_post)

        response = ollama.chat(
            model=self.model,
            messages=[{'role': 'user', 'content': prompt}]
        )

        keywords_str = response['message']['content'].strip()
        keywords = keywords_str.split()

        print(f"  Extracted keywords: {keywords}")
        return keywords

    def retrieve_chunks(self, keywords):
        """
        Perform both RAG and keyword search

        Args:
            keywords: List of keywords for keyword search

        Returns:
            tuple: (rag_chunks, keyword_chunks)
        """
        print("\n  Running RAG search...")
        rag_chunks = vector_search(self.session, self.embedding_model, self.piazza_post, self.class_name, self.professor, self.semester, self.limit)
        print(f"    Retrieved {len(rag_chunks)} chunks from RAG")

        print("\n  Running keyword search...")
        keyword_chunks = keyword_search(self.session, keywords, self.class_name, self.professor, self.semester, self.limit)
        print(f"    Retrieved {len(keyword_chunks)} chunks from keyword search")

        return rag_chunks, keyword_chunks

    def deduplicate_and_expand(self, rag_chunks, keyword_chunks):
        """
        Combine chunks, deduplicate, and expand to clusters

        Args:
            rag_chunks: Chunks from RAG search
            keyword_chunks: Chunks from keyword search

        Returns:
            list: Clusters with surrounding context
        """
        # Combine all chunks
        all_chunks = rag_chunks + keyword_chunks

        # Deduplicate by (url, chunk_index)
        seen = set()
        unique_chunks = []

        for chunk in all_chunks:
            key = (chunk['url'], chunk['chunk_index'])
            if key not in seen:
                seen.add(key)
                unique_chunks.append(chunk)

        print(f"\n  Combined and deduplicated to {len(unique_chunks)} unique chunks")

        # Expand chunks to clusters
        clusters = expand_chunks(self.session, unique_chunks, self.class_name, self.professor, self.semester)

        print(f"  Expanded to {len(clusters)} clusters")

        return clusters

    def check_cluster_relevance(self, clusters):
        """
        Check relevance of each cluster and generate summaries

        Args:
            clusters: List of cluster dicts with 'text' and 'metadata'

        Returns:
            list: List of relevant clusters with summaries added
        """
        relevant_clusters = []

        print(f"\n  Checking relevance of {len(clusters)} clusters...")

        for i, cluster in enumerate(clusters, 1):
            prompt = get_relevance_prompt(self.piazza_post, cluster['text'])

            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}]
            )

            summary = response['message']['content'].strip()

            print(summary)

            # Print relevance check progress
            if summary == "NOT RELEVANT":
                print(f"    Cluster {i}/{len(clusters)}: NOT RELEVANT")
            else:
                print(f"    Cluster {i}/{len(clusters)}: RELEVANT")
                relevant_clusters.append({
                    'text': cluster['text'],
                    'summary': summary,
                    'metadata': cluster['metadata']
                })

        print(f"\n  Found {len(relevant_clusters)} relevant clusters")
        return relevant_clusters

    @staticmethod
    def format_context_for_answer(relevant_clusters):
        """
        Format relevant clusters with citations for final answer generation

        Args:
            relevant_clusters: List of cluster dicts with summary and metadata

        Returns:
            str: Formatted context string
        """
        if not relevant_clusters:
            return ""

        context_parts = []
        for i, cluster in enumerate(relevant_clusters, 1):
            metadata = cluster['metadata']
            lecture_title = metadata.get('lecture_title', 'Unknown Lecture')
            timestamp = metadata.get('lecture_timestamp', '')

            citation = f"[Lecture: {lecture_title}"
            if timestamp:
                citation += f", Timestamp: {timestamp}"
            citation += "]"

            context_parts.append(f"{i}. {citation}\n{cluster['summary']}")

        return "\n\n".join(context_parts)
