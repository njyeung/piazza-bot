# Multi-Agent RAG Pipeline for Piazza Q&A

## Overview

This document describes a sophisticated multi-agent Retrieval-Augmented Generation (RAG) system designed to answer student questions on Piazza using lecture video transcripts. The system is optimized for **accuracy over speed**, leveraging local LLMs (Ollama Llama 3.1) with extensive verification and reasoning loops to compensate for smaller model limitations.

**Key Design Principles:**
- **No time constraints**: 15-20 minutes per question is acceptable for async responses
- **Hybrid retrieval**: Combines vector similarity + keyword matching for comprehensive recall
- **Multi-stage verification**: Progressive filtering and consistency checking
- **Parallel processing**: Multiple subagents run concurrently where possible
- **Tool use**: Agents can search and expand context dynamically
- **Citation tracking**: Maintain source attribution with video timestamps throughout

---

## Pipeline Architecture

### Stage 1: Question Understanding & Decomposition
**Duration**: ~30 seconds
**Agent**: Question Analyzer (Main Agent)
**Tools**: None
**Strategy**: Chain-of-thought reasoning

**Purpose**: Break down the student's question and prepare for diverse retrieval strategies.

**Tasks**:
1. Analyze the question structure and intent
2. Identify key concepts, entities, and technical terms
3. Decompose complex questions into sub-questions
4. Generate 3-5 alternative phrasings for semantic diversity
5. Classify question type (definition, comparison, how-to, debugging, conceptual, etc.)
6. Extract keywords for hybrid search

**Prompt Template**:
```
You are analyzing a student's question to prepare for searching lecture materials.

Question: {question}

Think step-by-step:
1. What is the student really asking? (Rephrase in your own words)
2. What are the key concepts/entities? (List them)
3. Can this be broken into sub-questions? (If complex)
4. Generate 3-5 alternative phrasings that preserve the meaning
5. What type of question is this? (definition/comparison/how-to/etc.)
6. What keywords would appear in a relevant answer? (For keyword search)

Output format:
INTENT: [concise restatement]
KEY_CONCEPTS: [concept1, concept2, concept3]
SUB_QUESTIONS: [q1, q2, q3] or "N/A"
REFORMULATIONS:
  1. [alternative phrasing 1]
  2. [alternative phrasing 2]
  3. [alternative phrasing 3]
  4. [alternative phrasing 4]
  5. [alternative phrasing 5]
QUESTION_TYPE: [type]
KEYWORDS: [keyword1, keyword2, keyword3]
```

**Output**:
- Original question
- 3-5 reformulated queries
- List of key concepts to verify in results
- Question classification
- Keywords for hybrid search

---

### Stage 2: Hybrid Multi-Query Retrieval
**Duration**: ~10 seconds
**Strategy**: Parallel vector + keyword search

**Purpose**: Cast a wide net using both semantic similarity and exact keyword matching.

**Process**:

#### 2A: Vector Search (for each reformulated question)
```python
for query in reformulated_questions:
    # Embed query
    query_vector = model.encode(query, normalize_embeddings=True)

    # Search Cassandra
    results = session.execute("""
        SELECT chunk_index, chunk_text, token_count, lecture_timestamp, lecture_title, url
        FROM embeddings
        WHERE class_name = ?
          AND professor = ?
          AND semester = ?
        ORDER BY embedding ANN OF ?
        LIMIT 15
    """, (class_name, professor, semester, query_vector.tolist()))

    vector_candidates.extend(results)
```

#### 2B: Keyword Search
```python
# Build keyword query (OR logic)
keyword_query = " OR ".join(keywords)

results = session.execute("""
    SELECT chunk_index, chunk_text, token_count, lecture_timestamp, lecture_title, url
    FROM embeddings
    WHERE class_name = ?
      AND professor = ?
      AND semester = ?
      AND chunk_text : ?
    LIMIT 30
""", (class_name, professor, semester, keyword_query))

keyword_candidates.extend(results)
```

#### 2C: Merge and Deduplicate
```python
# Combine results, deduplicate by (url, chunk_index)
all_candidates = merge_deduplicate(vector_candidates, keyword_candidates)
# Keep top 50 unique candidates based on score/frequency
top_candidates = rank_candidates(all_candidates, limit=50)
```

**Output**: ~50 unique candidate chunks (mix of semantic + keyword matches)

---

### Stage 3: Chunk Expansion
**Duration**: ~5 seconds
**Strategy**: Fetch surrounding context for top candidates

**Purpose**: Provide broader context by including neighboring chunks.

**Process**:
```python
expanded_passages = []

for chunk in top_30_candidates:
    # Fetch ±2 neighbor chunks
    context_chunks = session.execute("""
        SELECT chunk_index, chunk_text, lecture_timestamp
        FROM embeddings
        WHERE class_name = ?
          AND professor = ?
          AND semester = ?
          AND url = ?
          AND chunk_index >= ?
          AND chunk_index <= ?
        ORDER BY chunk_index ASC
    """, (class_name, professor, semester, chunk.url,
          chunk.chunk_index - 2, chunk.chunk_index + 2))

    # Merge into single passage
    passage = {
        'text': ' '.join([c.chunk_text for c in context_chunks]),
        'original_chunk_index': chunk.chunk_index,
        'lecture_title': chunk.lecture_title,
        'url': chunk.url,
        'timestamp': chunk.lecture_timestamp,
        'similarity_score': chunk.score  # from retrieval
    }
    expanded_passages.append(passage)
```

**Output**: 30 expanded passages with ±2 chunk context window

---

### Stage 4: Parallel Relevance Verification
**Duration**: ~5 minutes
**Agents**: 30 Relevance Verifier subagents (parallel)
**Tools**: None
**Strategy**: Binary classification with reasoning

**Purpose**: Filter out false positives from retrieval using LLM judgment.

**Process**: For each expanded passage, launch a subagent:

**Prompt Template**:
```
You are a teaching assistant verifying if a lecture excerpt is relevant to a student's question.

Original Question: {question}
Key Concepts: {key_concepts}
Keywords to look for: {keywords}

Lecture Excerpt:
Title: {lecture_title}
Timestamp: {timestamp}
---
{expanded_passage_text}
---

Think step-by-step:
1. What topics does this excerpt discuss?
2. Does it mention or explain any of the key concepts: {key_concepts}?
3. Does it provide information that helps answer the question?
4. Is this a direct answer, supporting context, or unrelated?

Respond with EXACTLY one of:
RELEVANT: [1-2 sentence reason why this helps answer the question]
NOT_RELEVANT: [1-2 sentence reason why this doesn't help]
```

**Parallel Execution**:
```python
from concurrent.futures import ThreadPoolExecutor

def verify_relevance(passage, question, key_concepts, keywords):
    prompt = build_relevance_prompt(passage, question, key_concepts, keywords)
    response = ollama.generate(model='llama3.1', prompt=prompt)
    return parse_relevance_response(response, passage)

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [
        executor.submit(verify_relevance, p, question, concepts, keywords)
        for p in expanded_passages
    ]
    verified_passages = [f.result() for f in futures if f.result()['relevant']]
```

**Output**: ~10-15 verified relevant passages with reasoning

---

### Stage 5: Parallel Information Extraction
**Duration**: ~5 minutes
**Agents**: 10-15 Information Extractor subagents (parallel)
**Tools**: None
**Strategy**: Structured fact extraction

**Purpose**: Extract specific, actionable information from each verified passage.

**Prompt Template**:
```
Extract specific information from this lecture excerpt that helps answer the student's question.

Question: {question}

Lecture Excerpt:
Title: {lecture_title}
Timestamp: {timestamp}
---
{passage_text}
---

Extract and categorize information:

1. DEFINITIONS: Key terms and their meanings
2. EXPLANATIONS: How concepts work or relate
3. EXAMPLES: Concrete instances or use cases
4. COMPARISONS: Similarities/differences between concepts
5. WARNINGS: Common mistakes or important caveats
6. PROCEDURES: Step-by-step processes

Format each fact as:
[CATEGORY] "Extracted fact or quote" (Lecture: {title}, Time: {timestamp})

Only extract facts directly relevant to answering the question.
```

**Output Example**:
```
[DEFINITION] "OLTP stands for Online Transaction Processing - handles individual database transactions like insert, update, delete" (Lecture: Database Systems, Time: 00:18:45)

[DEFINITION] "OLAP stands for Online Analytical Processing - designed for complex queries and data analysis" (Lecture: Database Systems, Time: 00:19:12)

[COMPARISON] "OLTP uses row-oriented storage because it needs to access complete records quickly. OLAP uses column-oriented storage because analytics queries typically access only specific columns across many rows" (Lecture: Storage Formats, Time: 00:22:30)

[EXAMPLE] "CSV is row-oriented (good for OLTP), Parquet is column-oriented (good for OLAP)" (Lecture: File Formats, Time: 00:25:10)
```

**Parallel Execution**:
```python
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [
        executor.submit(extract_information, p, question)
        for p in verified_passages
    ]
    extracted_facts = [f.result() for f in futures]

# Flatten and deduplicate facts
all_facts = []
for fact_list in extracted_facts:
    all_facts.extend(fact_list)
```

**Output**: Structured list of facts with source citations

---

### Stage 6: Cross-Reference & Consistency Check
**Duration**: ~2 minutes
**Agent**: Consistency Checker (ReAct agent)
**Tools**:
- `search_lectures(query)`: Perform additional searches
- `expand_chunk(url, chunk_index, window)`: Get more context

**Strategy**: ReAct (Reasoning + Acting) with search capability

**Purpose**: Identify contradictions, fill gaps, and verify consistency.

**Prompt Template**:
```
You are reviewing extracted facts from multiple lecture segments for consistency and completeness.

Original Question: {question}

Extracted Facts:
{structured_facts}

Available Tools:
1. search_lectures(query): Search for additional relevant chunks
2. expand_chunk(url, chunk_index, window): Get more context around a specific chunk

Think step-by-step and use tools as needed:

1. CONSISTENCY CHECK:
   - Are there any contradictions between facts?
   - Do facts from different lectures agree?

2. COMPLETENESS CHECK:
   - Are there gaps in the answer?
   - Is any part of the question unanswered?

3. VERIFICATION:
   - Should any facts be cross-referenced?
   - Should we search for additional information? (Use tools if yes)

Process:
Thought: [your reasoning]
Action: [tool_name(arguments)] or "None"
Observation: [tool result]
Thought: [reasoning about result]
... (repeat as needed)

Final Output:
ISSUES_FOUND: [List any contradictions or problems, or "None"]
GAPS: [List missing information, or "None"]
ADDITIONAL_FACTS: [Any new facts found via tools]
RECONCILIATION: [How contradictions were resolved, if any]
```

**Example Execution**:
```
Thought: The facts mention both row-oriented and column-oriented storage. Let me check if there are any contradictions in how they're described for OLAP vs OLTP.

Action: None (facts are consistent)

Thought: All facts agree that OLAP uses column-oriented and OLTP uses row-oriented. The question also asks specifically "which is column and which is row?" - this is fully answered.

Thought: Let me check if there are examples of real databases that use each type.

Action: search_lectures("OLAP database examples PostgreSQL Redshift")

Observation: [Found chunk mentioning Amazon Redshift as columnar OLAP database]

Final Output:
ISSUES_FOUND: None
GAPS: None - question is fully answered
ADDITIONAL_FACTS:
  [EXAMPLE] "Amazon Redshift is a column-oriented database designed for OLAP workloads" (Lecture: Cloud Data Warehouses, Time: 00:42:15)
RECONCILIATION: N/A
```

**Output**: Reconciled fact set + any additional context retrieved

---

### Stage 7: Answer Synthesis
**Duration**: ~3 minutes
**Agent**: Answer Composer (Main Agent)
**Tools**:
- `expand_chunk(url, chunk_index, window)`: Get more context
- `search_related(concept)`: Find related concepts

**Strategy**: Chain-of-thought with tool use

**Purpose**: Compose a comprehensive, well-structured answer with citations.

**Prompt Template**:
```
Synthesize a comprehensive answer to the student's question using verified facts.

Question: {question}
Key Concepts: {key_concepts}

Verified Facts (with citations):
{structured_facts}

Tools Available:
- expand_chunk(url, chunk_index, window): Get more context if needed
- search_related(concept): Search for related topics

Guidelines:
1. Directly answer all parts of the question
2. Organize logically (definitions first, then comparisons, then examples)
3. Include relevant examples from lectures
4. Add citations with video timestamps for each claim
5. Use clear, student-friendly language
6. If uncertain about something, use tools to clarify

Think step-by-step:
1. Outline the answer structure
2. Check if all parts of question are addressed
3. Identify any gaps (use tools if needed)
4. Draft the answer with inline citations
5. Review for clarity and completeness

Format:
[Your chain-of-thought reasoning]

FINAL ANSWER:
[The answer text with inline citations like (Lecture Title, 00:12:34)]
```

**Example Output**:
```
FINAL ANSWER:

OLAP and OLTP are two different types of database systems optimized for different use cases:

**OLTP (Online Transaction Processing)** handles individual database transactions like inserts, updates, and deletes (Database Systems, 00:18:45). It uses **row-oriented storage** because it needs to access complete records quickly (Storage Formats, 00:22:30). A common example of a row-oriented format is CSV (File Formats, 00:25:10).

**OLAP (Online Analytical Processing)** is designed for complex queries and data analysis (Database Systems, 00:19:12). It uses **column-oriented storage** because analytical queries typically access only specific columns across many rows, making column-oriented formats much more efficient (Storage Formats, 00:22:30). Parquet is a popular column-oriented format (File Formats, 00:25:10), and Amazon Redshift is an example of a column-oriented database designed for OLAP workloads (Cloud Data Warehouses, 00:42:15).

In summary:
- **OLTP = Row-oriented** (for transaction processing)
- **OLAP = Column-oriented** (for analytical queries)
```

**Output**: Complete answer with citations

---

### Stage 8: Verification & Quality Check
**Duration**: ~1 minute
**Agent**: Quality Verifier
**Tools**: `search_lectures(query)` (if verification needed)
**Strategy**: Critical evaluation

**Purpose**: Final check for accuracy, completeness, and clarity.

**Prompt Template**:
```
Review this answer for accuracy and quality before posting to Piazza.

Original Question: {question}
Proposed Answer: {answer}
Source Facts: {facts}

Checklist:
1. COMPLETENESS: Does it answer ALL parts of the question?
2. ACCURACY: Are there any factual errors or misinterpretations?
3. CITATIONS: Are all citations accurate and properly formatted?
4. CLARITY: Is it clear and easy to understand for students?
5. WARNINGS: Should any caveats or clarifications be added?

For each item, respond:
✓ [OK] or ✗ [ISSUE: specific problem and suggested fix]

If any issues found, provide:
REVISION_NEEDED: Yes/No
SUGGESTED_CHANGES: [Specific edits]
CONFIDENCE: High/Medium/Low

If confidence is Low, suggest flagging for TA review.
```

**Output**:
- Validated answer (approved for posting)
- OR revision suggestions
- OR flag for human review (if low confidence)

---

## Tools API Reference

### 1. `search_lectures(query, class_name, professor, semester, limit=20)`
**Purpose**: Perform hybrid vector + keyword search

**Implementation**:
```python
def search_lectures(query: str, class_name: str, professor: str,
                   semester: str, limit: int = 20) -> List[Chunk]:
    # Vector search
    query_vector = model.encode(query, normalize_embeddings=True)
    vector_results = session.execute("""
        SELECT * FROM embeddings
        WHERE class_name = ? AND professor = ? AND semester = ?
        ORDER BY embedding ANN OF ?
        LIMIT ?
    """, (class_name, professor, semester, query_vector.tolist(), limit))

    # Keyword search
    keywords = extract_keywords(query)
    keyword_query = " OR ".join(keywords)
    keyword_results = session.execute("""
        SELECT * FROM embeddings
        WHERE class_name = ? AND professor = ? AND semester = ?
          AND chunk_text : ?
        LIMIT ?
    """, (class_name, professor, semester, keyword_query, limit))

    # Merge and rank
    return merge_and_rank(vector_results, keyword_results, limit)
```

**Returns**: List of chunks with metadata (text, timestamp, lecture, url)

---

### 2. `expand_chunk(url, chunk_index, window_size=2)`
**Purpose**: Fetch neighboring chunks for context

**Implementation**:
```python
def expand_chunk(url: str, chunk_index: int, window_size: int = 2) -> str:
    chunks = session.execute("""
        SELECT chunk_text, chunk_index, lecture_timestamp
        FROM embeddings
        WHERE url = ?
          AND chunk_index >= ?
          AND chunk_index <= ?
        ORDER BY chunk_index ASC
    """, (url, chunk_index - window_size, chunk_index + window_size))

    return {
        'text': ' '.join([c.chunk_text for c in chunks]),
        'start_time': chunks[0].lecture_timestamp,
        'end_time': chunks[-1].lecture_timestamp,
        'chunk_range': f"{chunks[0].chunk_index}-{chunks[-1].chunk_index}"
    }
```

**Returns**: Expanded passage with time range

---

### 3. `search_related(concept, class_name, professor, semester, limit=10)`
**Purpose**: Find chunks about related or mentioned concepts

**Implementation**:
```python
def search_related(concept: str, class_name: str, professor: str,
                  semester: str, limit: int = 10) -> List[Chunk]:
    # Embed the concept
    concept_vector = model.encode(f"What is {concept}?", normalize_embeddings=True)

    # Search
    results = session.execute("""
        SELECT * FROM embeddings
        WHERE class_name = ? AND professor = ? AND semester = ?
        ORDER BY embedding ANN OF ?
        LIMIT ?
    """, (class_name, professor, semester, concept_vector.tolist(), limit))

    return list(results)
```

**Returns**: Chunks related to the concept

---

### 4. `get_chunk_by_id(url, chunk_index)`
**Purpose**: Fetch a specific chunk by its identifier

**Implementation**:
```python
def get_chunk_by_id(url: str, chunk_index: int) -> Chunk:
    result = session.execute("""
        SELECT * FROM embeddings
        WHERE url = ? AND chunk_index = ?
    """, (url, chunk_index))

    return result.one()
```

**Returns**: Single chunk with all metadata

---

## Technology Stack

### Core Components
- **LLM**: Ollama (Llama 3.1 8B) - Local deployment
- **Embeddings**: Sentence Transformers (thenlper/gte-large, 1024-dim)
- **Vector DB**: Cassandra 5.0+ with SAI indexes
- **Orchestration**: Python 3.10+
- **Parallelization**: `concurrent.futures.ThreadPoolExecutor`

### Dependencies
```bash
# Python packages
pip install sentence-transformers cassandra-driver ollama python-dotenv

# Ollama model
ollama pull llama3.1
```

### Database Indexes
- **Vector Index**: `embeddings_ann_idx` on `embedding` column (ANN search)
- **Text Index**: `embeddings_text_idx` on `chunk_text` column (keyword search)

---

## Execution Timeline

**Total time per question**: 15-20 minutes

| Stage | Duration | Parallelizable | Resource |
|-------|----------|----------------|----------|
| 1. Question Analysis | 30s | No | 1 LLM call |
| 2. Hybrid Retrieval | 10s | Yes (DB queries) | Cassandra |
| 3. Chunk Expansion | 5s | Yes (DB queries) | Cassandra |
| 4. Relevance Verification | 5min | **Yes (30 agents)** | 30 LLM calls |
| 5. Information Extraction | 5min | **Yes (15 agents)** | 15 LLM calls |
| 6. Consistency Check | 2min | No (with tools) | 1-3 LLM calls |
| 7. Answer Synthesis | 3min | No (with tools) | 1-2 LLM calls |
| 8. Quality Check | 1min | No | 1 LLM call |

**Parallelization Strategy**:
- Run Stage 4 subagents in batches of 10 (to avoid overwhelming GPU)
- Run Stage 5 subagents in batches of 10
- Total LLM calls: ~50-55 per question

---

## Error Handling & Fallbacks

### Stage 4: No Relevant Chunks Found
**Scenario**: All 30 passages marked NOT_RELEVANT

**Fallback**:
1. Broaden search: Increase retrieval limit to top 50
2. Relax relevance threshold: Accept "partially relevant" passages
3. Try expanded keyword search with synonyms
4. If still no results: Return "Insufficient lecture coverage on this topic" with suggestion to ask TA

### Stage 6: Contradictions Found
**Scenario**: Facts from different lectures contradict

**Fallback**:
1. Expand both contradicting chunks to get full context
2. Search for clarifying information
3. If unresolved: Present both perspectives with citations, note discrepancy
4. Flag for TA review

### Stage 8: Low Confidence
**Scenario**: Quality verifier rates confidence as "Low"

**Fallback**:
1. Do NOT auto-post to Piazza
2. Save draft answer for TA review
3. Flag question for human verification
4. Optionally: Send draft to TA via email/Slack for approval

### GPU/Ollama Errors
**Scenario**: Ollama timeout or GPU out of memory

**Fallback**:
1. Retry with exponential backoff (3 attempts)
2. Reduce batch size in parallel stages
3. If persistent: Queue question for later processing
4. Log error and notify admin

---

## Configuration

### Environment Variables
```bash
# Cassandra
CASSANDRA_HOSTS=localhost
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=transcript_db

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1

# Embedding Model
EMBEDDING_MODEL=thenlper/gte-large

# Pipeline Settings
MAX_PARALLEL_AGENTS=10
RELEVANCE_THRESHOLD=0.7
CHUNK_EXPANSION_WINDOW=2
RETRIEVAL_LIMIT=50
```

### Tuneable Parameters
- `MAX_PARALLEL_AGENTS`: How many subagents to run concurrently (default: 10)
- `CHUNK_EXPANSION_WINDOW`: How many chunks before/after to include (default: 2)
- `RETRIEVAL_LIMIT`: Top-k chunks to retrieve initially (default: 50)
- `RELEVANCE_THRESHOLD`: Minimum confidence for relevance (not currently used, binary system)

---

## Example Query Flow

**Input**: "What is the difference between OLAP and OLTP? Which one is column-oriented?"

**Stage 1 Output**:
```
KEY_CONCEPTS: [OLAP, OLTP, column-oriented, row-oriented, database systems]
REFORMULATIONS:
  1. "Explain OLAP vs OLTP and their storage formats"
  2. "How do OLAP and OLTP differ in terms of data organization?"
  3. "Which database type uses columnar storage: OLAP or OLTP?"
KEYWORDS: [OLAP, OLTP, column, row, columnar, storage, oriented]
```

**Stage 2 Output**: 50 chunks (35 from vector search, 30 from keyword search, 15 overlap)

**Stage 3 Output**: 30 expanded passages with ±2 chunk context

**Stage 4 Output**: 12 passages marked RELEVANT

**Stage 5 Output**: 18 extracted facts with citations

**Stage 6 Output**: No contradictions, all facts consistent, 1 additional example found

**Stage 7 Output**: 200-word answer with 6 inline citations

**Stage 8 Output**: ✓ Approved, Confidence: High

**Posted to Piazza**: Final answer with video timestamp links

---

## Future Enhancements

### Phase 2: Multi-Turn Conversations
- Allow students to ask follow-up questions
- Maintain conversation context across turns
- Reference previous answers in thread

### Phase 3: Proactive Suggestions
- Monitor Piazza for unanswered questions
- Automatically suggest draft answers to TAs
- Identify frequently asked topics for lecture improvement

### Phase 4: Multi-Modal
- Include slides/diagrams from lectures
- Generate visual aids for explanations
- Link to specific video frames with annotations

### Phase 5: Continuous Learning
- Track which answers get endorsed by TAs
- Fine-tune retrieval based on successful answers
- Build FAQ database from verified Q&A pairs

---

## Metrics & Monitoring

**Success Metrics**:
- Answer accuracy (TA endorsement rate)
- Answer completeness (% of question addressed)
- Citation accuracy (% of timestamps that are relevant)
- Student satisfaction (upvotes, follow-up clarity)

**Performance Metrics**:
- End-to-end latency (target: <20 min)
- Stage-wise timing breakdown
- Retrieval precision/recall
- LLM token usage and cost

**Logging**:
- Log all agent interactions and tool calls
- Store full pipeline state for debugging
- Track which chunks contributed to final answers
- Monitor error rates and fallback triggers

---

## Development Roadmap

**MVP (Phase 1)**:
- [ ] Implement core 8-stage pipeline
- [ ] Build tool API (search, expand, get_chunk)
- [ ] Create Ollama integration with retry logic
- [ ] Test on 10 sample questions
- [ ] Measure accuracy vs GPT-4 baseline

**Beta (Phase 2)**:
- [ ] Add human-in-loop review queue
- [ ] Implement confidence scoring
- [ ] Build Piazza API integration
- [ ] Deploy to staging environment
- [ ] Run A/B test with TAs reviewing answers

**Production (Phase 3)**:
- [ ] Full Piazza automation
- [ ] Monitoring dashboard
- [ ] Error alerting system
- [ ] Scale to multiple courses
- [ ] Continuous improvement pipeline
