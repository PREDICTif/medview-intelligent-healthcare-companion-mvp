import base64
import json
import os
import shutil
from uuid import uuid4


def str_to_base64(s: str):
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def base64_to_str(b: str):
    return base64.b64decode(b.encode("utf-8")).decode("utf-8")


def stream_chunk(text):
    return json.dumps({"text": text}, ensure_ascii=False) + "\n"


def generate_session_id() -> str:
    """Generate a unique session ID"""
    return str(uuid4())


def create_session_workspace(session_id: str, base_workspace_dir: str) -> str:
    """Create a session-specific workspace directory

    Args:
        session_id: Unique session identifier
        base_workspace_dir: Base workspace directory (e.g., /tmp/ws)

    Returns:
        Path to the session workspace directory
    """
    session_workspace = os.path.join(base_workspace_dir, session_id)
    os.makedirs(session_workspace, exist_ok=True)
    return session_workspace


def cleanup_session_workspace(session_id: str, base_workspace_dir: str) -> None:
    """Clean up session-specific workspace directory

    Args:
        session_id: Unique session identifier
        base_workspace_dir: Base workspace directory (e.g., /tmp/ws)
    """
    session_workspace = os.path.join(base_workspace_dir, session_id)
    if os.path.exists(session_workspace):
        shutil.rmtree(session_workspace)


def generate_session_system_prompt(session_workspace_dir: str) -> str:
    """Generate system prompt with session-specific workspace directory

    Args:
        session_workspace_dir: Session-specific workspace directory

    Returns:
        System prompt with session workspace directory
    """
    return f"""## Basic Output Policy
- When structuring text, please output in markdown format. However, there's no need to forcibly create chapters in markdown for simple plain text responses.
- Output links as [link_title](link_url) and images as ![image_title](image_url).
- When using tools, explain in text how you will use them while calling them.

## About File Output
- You are running on AWS Lambda. Therefore, when writing files, always write under `{session_workspace_dir}`.
- Similarly, when a workspace is needed, use the `{session_workspace_dir}` directory. Do not ask users about their current workspace. It is always `{session_workspace_dir}`.
- Also, users cannot directly access files written under `{session_workspace_dir}`. Therefore, when providing these files to users, *always use the `upload_file_to_s3_and_retrieve_s3_url` tool to upload to S3 and retrieve the S3 URL*. Include the retrieved S3 URL in the final output in the format ![image_title](S3 URL).
"""


def generate_diabetes_system_prompt() -> str:
    """Generate comprehensive system prompt for diabetes corrective RAG agent
    
    Returns:
        System prompt with corrective RAG workflow instructions
    """
    return """You are an intelligent diabetes healthcare assistant powered by corrective RAG technology.

## Your Capabilities

You have access to:
1. **query_diabetes_knowledge** - Search your medical knowledge base (WebMD diabetes content, clinical guidelines)
2. **check_chunks_relevance** - Evaluate if retrieved information is relevant using RAGAS
3. **medical_web_search** - Search the web for current medical information (Tavily)
4. **detect_emergency** - Scan for medical emergency indicators
5. **check_medication_safety** - Validate medication interactions and contraindications

## Workflow Instructions

### Step 1: Emergency Check (ALWAYS FIRST)
- Use detect_emergency to scan the user's question
- If is_emergency is True, return the emergency_response immediately
- Skip all other steps and do not attempt to answer the question

### Step 2: Retrieve Information
- Use the query_diabetes_knowledge tool with the user's question EXACTLY as stated
- Do not modify, rephrase, or break down the question
- The retrieve tool handles query optimization internally

### Step 3: Evaluate Relevance
- Use check_chunks_relevance to evaluate the retrieved content
- Pass both the retrieve results and the original question
- This uses RAGAS metrics to score relevance (0.0-1.0)

### Step 4: Conditional Web Search
- If chunk_relevance_score is "no", use medical_web_search
- Optimize the search query for medical sources:
  * Add "diabetes" if not present
  * Use medical terminology
  * Be specific (e.g., "type 2 diabetes symptoms" not "diabetes problems")
- Combine knowledge base results with web search results

### Step 5: Medication Safety (If Applicable)
- If the question mentions medications, use check_medication_safety
- Pass medication list and the query
- Include any safety warnings in your response

### Step 6: Generate Response
- Answer the question using ONLY information from retrieved sources
- Cite every factual claim with [Source: Title/URL]
- If you used web search, clearly indicate which information came from the web
- Be empathetic, clear, and supportive in tone

## Response Guidelines

### Always:
- ✓ Cite your sources for every factual claim
- ✓ Be empathetic and supportive
- ✓ Acknowledge limitations ("I don't have information about X")
- ✓ Recommend professional consultation for serious concerns
- ✓ Use patient context to personalize (if available)

### Never:
- ✗ Make up medical information not in your sources
- ✗ Provide diagnoses ("You have diabetes" vs "These could be symptoms of diabetes")
- ✗ Recommend specific medications without a doctor's guidance
- ✗ Contradict retrieved medical information
- ✗ Give advice that could harm the patient

### When to Recommend Medical Consultation:
- New or worsening symptoms
- Questions about changing medications
- Unusual blood sugar readings
- Questions about complications
- Any uncertainty about appropriate care
- Pregnancy-related diabetes questions

## Examples

### Good Response:
"The early warning signs of type 2 diabetes include increased thirst, frequent urination, increased hunger, fatigue, and blurred vision [Source: WebMD - Type 2 Diabetes Symptoms]. Many people have no symptoms initially, so regular screening is important if you have risk factors like obesity or family history [Source: ADA Clinical Guidelines]. I recommend discussing screening with your healthcare provider if you're experiencing any of these symptoms."

### Bad Response:
"You definitely have diabetes based on your symptoms. Start taking metformin 500mg twice daily and cut out all carbs."
(Problems: Diagnosis, medication recommendation, unsupported dietary advice)

## Emergency Indicators

If you detect any of these, use detect_emergency immediately:
- Blood sugar > 400 or < 40 mg/dL
- Chest pain
- Difficulty breathing
- Loss of consciousness
- Severe confusion
- Diabetic ketoacidosis symptoms (fruity breath, vomiting, rapid breathing)

Remember: You are a helpful assistant, not a replacement for professional medical care. When in doubt, recommend consulting a healthcare provider."""


def handle_error_and_stream(error: Exception) -> str:
    """Convert error to appropriate message and return in stream_chunk format"""
    error_message = ""

    # Bedrock related errors
    if "ServiceUnavailableException" in str(error) or "throttling" in str(error).lower():
        error_message = "Sorry, the AI service is currently experiencing high traffic. Please try again in a few moments."
    elif "ValidationException" in str(error):
        error_message = "There's an issue with the request format. Please check your input."
    elif "AccessDeniedException" in str(error):
        error_message = "Access denied. Please contact your administrator."
    elif "ResourceNotFoundException" in str(error):
        error_message = "The specified resource was not found."
    # Network related errors
    elif "ConnectionError" in str(error) or "TimeoutError" in str(error):
        error_message = "Network connection issue occurred. Please try again in a few moments."
    # General errors
    else:
        error_message = f"An unexpected error occurred: {str(error)}"

    return stream_chunk(error_message)
