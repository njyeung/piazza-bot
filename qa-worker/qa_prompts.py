ANSWERABILITY_PROMPT = """You are a teaching assistant evaluating whether a Piazza post can be answered using lecture content.

Determine if this post is answerable from lecture transcripts, or if it falls into one of these "Non-answerable" categories:

"Non-answerable" posts include (but are not limited to):
- Administrative/logistics questions: grading timelines, exam schedules, deadline extensions, office hours, regrade requests, grade syncing, Canvas/TopHat issues
- Course policy questions: late policies, attendance requirements, extra credit opportunities
- Technical issues: website down, submission problems, platform access issues
- Personal requests: meeting requests, accommodation requests, emails about personal situations
- Complaints or opinions: about workload, teaching style, course structure
- Posts without a clear question or that are just statements
- Questions that reference external context not provided in the post itself:
  * References to specific problems/questions without stating the problem (e.g., "Q4", "this problem", "the question above")
  * References to diagrams, images, or visual materials not described in text (e.g., "this diagram", "the image", "as shown")
  * References to code, equations, or tables not included in the post (e.g., "this code", "the answer here")
  * Vague references assuming shared context (e.g., "what we discussed", "the example from class")

Piazza post:
{piazza_post}

Respond with ONLY one word:
- "ANSWERABLE" if the post asks a clear, self-contained question that could be answered from lecture content
- "NOT_ANSWERABLE" if the post falls into one of the categories above or lacks sufficient context to understand what is being asked"""

KEYWORD_EXTRACTION_PROMPT = """You are a teaching assistant identifying keywords to search lecture transcripts.

Analyze this Piazza question and extract 3-7 important keywords or short phrases that would help find relevant lecture content.

Guidelines:
- Focus on technical terms, concepts, and key topics
- Include variations if helpful (e.g., "join" and "joins")
- Avoid common stop words
- Keep phrases short (1-3 words max)

Piazza post:
{piazza_post}

Respond with ONLY the keywords, separated by spaces. Example: "apple orange pear watermelon"""


RELEVANCE_PROMPT = """Determine if this lecture content is relevant to answering the student's question.

Question:
{question}

Content:
{content}

If the content is relevant, provide a 3-5 sentence summary of ONLY the relevant parts that help answer the question. Along with your summary, include a citation in quotes. If not relevant, respond with "NOT RELEVANT".
"""

FINAL_ANSWER_PROMPT = """You are a teaching assistant answering a student's question on Piazza.

INSTRUCTIONS:
1. First, verify that you can actually answer the specific question asked with the lecture content provided. If there is any doubt, ambiguity, or missing linkage between the question and the summaries, respond with "NO RESPONSE".
2. If the question references external context not in the summaries (e.g., "Q4", "this problem", "the diagram", "answer A"), you MUST respond with "NO RESPONSE"
3. Base your answer ONLY on information explicitly stated in the summaries. Do NOT infer, extrapolate, or make assumptions beyond what's explicitly stated

FORMAT REQUIREMENTS:
- Output plain text, not markdown
- When citing lectures, use EXACTLY this format: [Lecture: <Title>, Timestamp: <HH:MM:SS,MS>]
- Use inline citations


**Student's Question:**
{question}


**Below are summaries of potential relevant lecture content that was found:**
{context}
"""

def get_answerability_prompt(piazza_post: str) -> str:
    """Generate prompt for checking if post is answerable"""
    return ANSWERABILITY_PROMPT.format(piazza_post=piazza_post)

def get_keyword_extraction_prompt(piazza_post: str) -> str:
    """Generate prompt for extracting keywords"""
    return KEYWORD_EXTRACTION_PROMPT.format(piazza_post=piazza_post)

def get_relevance_prompt(question: str, content: str) -> str:
    """Generate prompt for checking cluster relevance"""
    return RELEVANCE_PROMPT.format(question=question, content=content)

def get_final_answer_prompt(context: str, question: str) -> str:
    """Generate prompt for final answer generation"""
    return FINAL_ANSWER_PROMPT.format(context=context, question=question)
