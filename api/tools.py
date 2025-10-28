import asyncio
import json
import logging
import re
from contextvars import ContextVar
from typing import Dict, List

import requests
from strands import tool

from config import TAVILY_API_KEY
from s3 import upload_file_to_s3

# Context variable to store session workspace directory
session_workspace_context: ContextVar[str] = ContextVar("session_workspace_context", default=None)


def create_session_aware_upload_tool(session_workspace_dir: str, x_user_sub: str = None):
    """Create a session-aware upload tool with the session workspace directory"""

    @tool
    def upload_file_to_s3_and_retrieve_s3_url(filepath: str, user_sub: str = None) -> str:
        """Upload the file at session workspace and retrieve the s3 path

        Args:
            filepath: The path to the uploading file
            user_sub: User subscription ID for gallery tracking
        """
        # Use provided user_sub or fall back to the session user_sub
        effective_user_sub = user_sub or x_user_sub
        return upload_file_to_s3(filepath, session_workspace_dir, effective_user_sub)

    return upload_file_to_s3_and_retrieve_s3_url


@tool
def get_weather(location: str, units: str = "metric") -> str:
    """Get current weather information for a specific location
    
    Args:
        location: City name, state/country (e.g., "New York, NY" or "London, UK")
        units: Temperature units - "metric" (Celsius), "imperial" (Fahrenheit), or "kelvin"
    """
    import os
    
    # Get API key from environment variable
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    
    if not api_key:
        return "Weather functionality is not available. OpenWeatherMap API key is not configured."
    
    try:
        # OpenWeatherMap Current Weather API
        base_url = "http://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": api_key,
            "units": units
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract relevant weather information
            weather_info = {
                "location": f"{data['name']}, {data['sys']['country']}",
                "temperature": data['main']['temp'],
                "feels_like": data['main']['feels_like'],
                "humidity": data['main']['humidity'],
                "pressure": data['main']['pressure'],
                "description": data['weather'][0]['description'].title(),
                "wind_speed": data.get('wind', {}).get('speed', 'N/A'),
                "visibility": data.get('visibility', 'N/A'),
                "units": units
            }
            
            # Format the response
            unit_symbol = "°C" if units == "metric" else "°F" if units == "imperial" else "K"
            wind_unit = "m/s" if units == "metric" else "mph" if units == "imperial" else "m/s"
            
            weather_report = f"""
Current Weather for {weather_info['location']}:
🌡️ Temperature: {weather_info['temperature']}{unit_symbol} (feels like {weather_info['feels_like']}{unit_symbol})
🌤️ Conditions: {weather_info['description']}
💧 Humidity: {weather_info['humidity']}%
🌬️ Wind Speed: {weather_info['wind_speed']} {wind_unit}
📊 Pressure: {weather_info['pressure']} hPa
👁️ Visibility: {weather_info['visibility']} meters
"""
            return weather_report.strip()
            
        elif response.status_code == 404:
            return f"Location '{location}' not found. Please check the spelling and try again."
        else:
            return f"Weather service error: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return "Weather service request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"Error connecting to weather service: {str(e)}"
    except Exception as e:
        return f"Unexpected error getting weather data: {str(e)}"


@tool
def get_weather_forecast(location: str, days: int = 5, units: str = "metric") -> str:
    """Get weather forecast for a specific location
    
    Args:
        location: City name, state/country (e.g., "New York, NY" or "London, UK")
        days: Number of days for forecast (1-5)
        units: Temperature units - "metric" (Celsius), "imperial" (Fahrenheit), or "kelvin"
    """
    import os
    
    # Get API key from environment variable
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    
    if not api_key:
        return "Weather forecast functionality is not available. OpenWeatherMap API key is not configured."
    
    # Limit days to reasonable range
    days = max(1, min(days, 5))
    
    try:
        # OpenWeatherMap 5-day forecast API
        base_url = "http://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": location,
            "appid": api_key,
            "units": units,
            "cnt": days * 8  # 8 forecasts per day (every 3 hours)
        }
        
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            unit_symbol = "°C" if units == "metric" else "°F" if units == "imperial" else "K"
            
            forecast_report = f"Weather Forecast for {data['city']['name']}, {data['city']['country']}:\n\n"
            
            # Group forecasts by day
            from datetime import datetime
            current_date = None
            
            for item in data['list'][:days * 8]:
                forecast_time = datetime.fromtimestamp(item['dt'])
                forecast_date = forecast_time.strftime('%Y-%m-%d')
                
                # Only show one forecast per day (around noon)
                if forecast_date != current_date and forecast_time.hour >= 12:
                    current_date = forecast_date
                    
                    temp = item['main']['temp']
                    temp_min = item['main']['temp_min']
                    temp_max = item['main']['temp_max']
                    description = item['weather'][0]['description'].title()
                    humidity = item['main']['humidity']
                    
                    day_name = forecast_time.strftime('%A, %B %d')
                    
                    forecast_report += f"📅 {day_name}:\n"
                    forecast_report += f"   🌡️ {temp}{unit_symbol} (Low: {temp_min}{unit_symbol}, High: {temp_max}{unit_symbol})\n"
                    forecast_report += f"   🌤️ {description}\n"
                    forecast_report += f"   💧 Humidity: {humidity}%\n\n"
            
            return forecast_report.strip()
            
        elif response.status_code == 404:
            return f"Location '{location}' not found. Please check the spelling and try again."
        else:
            return f"Weather forecast service error: {response.status_code} - {response.text}"
            
    except requests.exceptions.Timeout:
        return "Weather forecast service request timed out. Please try again."
    except requests.exceptions.RequestException as e:
        return f"Error connecting to weather forecast service: {str(e)}"
    except Exception as e:
        return f"Unexpected error getting weather forecast: {str(e)}"


@tool
def query_diabetes_knowledge(question: str) -> str:
    """Retrieve diabetes information from medical knowledge base
    
    Args:
        question: Question about diabetes (symptoms, treatments, management, etc.)
    """
    import os
    import boto3
    
    # Get Knowledge Base ID from environment variable
    knowledge_base_id = os.environ.get("DIABETES_KB_ID", "")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    min_score = float(os.environ.get("DIABETES_KB_MIN_SCORE", "0.5"))
    logging.info(f"Knowledge base ID: {knowledge_base_id}")
    logging.info(f"AWS region: {aws_region}")
    logging.info(f"Min score: {min_score}")
    
    if not knowledge_base_id:
        return "Diabetes knowledge base is not configured. Please contact your administrator."
    
    try:
        # Create Bedrock Agent Runtime client
        bedrock_agent = boto3.client(
            service_name="bedrock-agent-runtime",
            region_name=aws_region
        )
        
        # Retrieve relevant information from knowledge base
        response = bedrock_agent.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={
                "text": question
            },
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": 5,
                    "overrideSearchType": "HYBRID"
                }
            }
        )
        
        # Extract and format results
        if "retrievalResults" not in response or len(response["retrievalResults"]) == 0:
            return "No relevant diabetes information found for your question. Please try rephrasing or ask a different question."
        
        results_text = "Based on medical knowledge sources:\n\n"
        
        for idx, result in enumerate(response["retrievalResults"], 1):
            score = result.get("score", 0)
            
            # Only include results above minimum score
            if score < min_score:
                continue
            
            content = result.get("content", {}).get("text", "")
            location = result.get("location", {})
            source_uri = location.get("s3Location", {}).get("uri", "Unknown source")
            
            results_text += f"**Source {idx}** (relevance: {score:.2f})\n"
            results_text += f"{content}\n\n"
            results_text += f"*Reference: {source_uri}*\n\n"
        
        if results_text == "Based on medical knowledge sources:\n\n":
            return "No sufficiently relevant diabetes information found. Please try rephrasing your question."
        
        return results_text.strip()
        
    except Exception as e:
        logging.error(f"Knowledge base access error: {type(e).__name__}: {str(e)}")
        logging.error(f"Knowledge base ID: {knowledge_base_id}, Region: {aws_region}")
        return f"Error accessing diabetes knowledge base: {str(e)}"


@tool
def query_diabetes_with_generation(question: str) -> str:
    """Get comprehensive AI-generated answer about diabetes with citations
    
    Args:
        question: Question about diabetes (symptoms, treatments, management, etc.)
    """
    import os
    import boto3
    
    # Get Knowledge Base ID from environment variable
    knowledge_base_id = os.environ.get("DIABETES_KB_ID", "")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    model_arn = f"arn:aws:bedrock:{aws_region}::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0"
    
    if not knowledge_base_id:
        return "Diabetes knowledge base is not configured. Please contact your administrator."
    
    try:
        # Create Bedrock Agent Runtime client
        bedrock_agent = boto3.client(
            service_name="bedrock-agent-runtime",
            region_name=aws_region
        )
        
        # Retrieve and generate comprehensive answer
        response = bedrock_agent.retrieve_and_generate(
            input={
                "text": question
            },
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledge_base_id,
                    "modelArn": model_arn,
                    "retrievalConfiguration": {
                        "vectorSearchConfiguration": {
                            "numberOfResults": 5,
                            "overrideSearchType": "HYBRID"
                        }
                    }
                }
            }
        )
        
        # Extract generated answer and citations
        output = response.get("output", {})
        answer_text = output.get("text", "No answer generated.")
        
        # Format citations
        citations = response.get("citations", [])
        if citations:
            answer_text += "\n\n**Sources:**\n"
            for idx, citation in enumerate(citations, 1):
                for reference in citation.get("retrievedReferences", []):
                    location = reference.get("location", {})
                    source_uri = location.get("s3Location", {}).get("uri", "Unknown source")
                    answer_text += f"{idx}. {source_uri}\n"
        
        return answer_text
        
    except Exception as e:
        logging.error(f"Knowledge base generation error: {type(e).__name__}: {str(e)}")
        logging.error(f"Knowledge base ID: {knowledge_base_id}, Region: {aws_region}, Model: {model_arn}")
        return f"Error generating diabetes answer: {str(e)}"


@tool
def web_search(keyword: str) -> str:
    """Search web by using Tavily API

    Args:
        keyword: Search word
    """

    if len(TAVILY_API_KEY) == 0:
        return "Web search functionality is not available because there is no API Key."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}",
    }

    body = {
        "query": keyword,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": True,
        "max_results": 5,
    }

    res = requests.post(
        "https://api.tavily.com/search",
        data=json.dumps(body, ensure_ascii=False),
        headers=headers,
    )

    return res.text


@tool
def check_chunks_relevance(results: str, question: str) -> Dict:
    """Evaluates the relevance of retrieved chunks to the user question using RAGAS.
    
    Uses the LLMContextPrecisionWithoutReference metric which measures how well
    the retrieved contexts align with the question without needing a reference answer.
    
    Args:
        results (str): Retrieval output from retrieve tool with 'Score:' and 'Content:' patterns
        question (str): Original user question
    
    Returns:
        dict: {
            "chunk_relevance_score": "yes" or "no",
            "chunk_relevance_value": float (0.0-1.0)
        }
    """
    import os
    
    try:
        from ragas import SingleTurnSample
        from ragas.metrics import LLMContextPrecisionWithoutReference
        from ragas.llms import LangchainLLMWrapper
        from langchain_aws import ChatBedrockConverse
        
        if not results or not isinstance(results, str):
            raise ValueError("Invalid input: 'results' must be a non-empty string.")
        if not question or not isinstance(question, str):
            raise ValueError("Invalid input: 'question' must be a non-empty string.")
        
        # Extract content chunks using regex pattern
        # Matches "Score: X.XX\nContent: <text>" and captures the text
        pattern = r"Score:.*?\nContent:\s*(.*?)(?=Score:|\Z)"
        docs = [chunk.strip() for chunk in re.findall(pattern, results, re.DOTALL)]
        
        if not docs:
            raise ValueError("No valid content chunks found in 'results'.")
        
        print(f"Extracted {len(docs)} chunks for relevance evaluation")
        
        # Initialize RAGAS evaluation model
        eval_model_id = os.environ.get("BEDROCK_EVAL_MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
        aws_region = os.environ.get("AWS_REGION", "us-east-1")
        
        thinking_params = {
            "thinking": {
                "type": "disabled"
            }
        }
        
        llm_for_evaluation = ChatBedrockConverse(
            model_id=eval_model_id,
            region_name=aws_region,
            additional_model_request_fields=thinking_params
        )
        llm_for_evaluation = LangchainLLMWrapper(llm_for_evaluation)
        
        # Prepare RAGAS evaluation sample
        sample = SingleTurnSample(
            user_input=question,
            response="placeholder-response",  # Required by RAGAS but not used for this metric
            retrieved_contexts=docs
        )
        
        # Evaluate using context precision metric
        scorer = LLMContextPrecisionWithoutReference(llm=llm_for_evaluation)
        score = asyncio.run(scorer.single_turn_ascore(sample))
        
        print("------------------------")
        print("Context evaluation")
        print("------------------------")
        print(f"chunk_relevance_value: {score}")
        print(f"chunk_relevance_score: {'yes' if score > 0.5 else 'no'}")
        
        # Binary decision: relevant if score > 0.5
        return {
            "chunk_relevance_score": "yes" if score > 0.5 else "no",
            "chunk_relevance_value": score
        }
    
    except Exception as e:
        print(f"Error in relevance check: {e}")
        # On error, assume relevant to be safe (better to over-retrieve in healthcare)
        return {
            "error": str(e),
            "chunk_relevance_score": "yes",  # Fail-safe: assume relevant
            "chunk_relevance_value": 0.5
        }


@tool
def medical_web_search(query: str) -> str:
    """Perform medical web search using Tavily API for authoritative health information.
    Only to be used if chunk_relevance_score is "no".
    
    Searches authoritative medical sources:
    - diabetes.org (American Diabetes Association)
    - cdc.gov, nih.gov
    - mayoclinic.org, webmd.com
    - pubmed.ncbi.nlm.nih.gov
    
    Args:
        query (str): The user question or medical search query
    
    Returns:
        str: Formatted search results with sources
    """
    import os
    
    if len(TAVILY_API_KEY) == 0:
        return "Medical web search functionality is not available because there is no API Key."
    
    print("---MEDICAL WEB SEARCH---")
    print(f"Query: {query}")
    
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        
        # Set API key for langchain tool
        os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
        
        # Initialize Tavily search tool
        web_search_tool = TavilySearchResults(k=3)
        
        # Perform web search
        search_results = web_search_tool.invoke({"query": query})
        
        print(f"Found {len(search_results)} web results")
        
        # Format results
        formatted_results = "**Web Search Results:**\n\n"
        
        for idx, result in enumerate(search_results, 1):
            content = result.get("content", "")
            url = result.get("url", "Unknown URL")
            title = result.get("title", "Unknown Title")
            score = result.get("score", 0.5)
            
            formatted_results += f"**Source {idx}** (relevance: {score:.2f})\n"
            formatted_results += f"**Title:** {title}\n"
            formatted_results += f"{content}\n\n"
            formatted_results += f"*Reference: {url}*\n\n"
        
        return formatted_results.strip()
        
    except Exception as e:
        print(f"Error in medical web search: {e}")
        return f"Error performing medical web search: {str(e)}"


@tool
def detect_emergency(query: str) -> Dict:
    """Scans user query for emergency medical indicators related to diabetes.
    
    Emergency Indicators:
    - Severe hyperglycemia (blood sugar > 400 mg/dL)
    - Severe hypoglycemia (blood sugar < 40 mg/dL)
    - Diabetic ketoacidosis (DKA) symptoms
    - Cardiac symptoms with diabetes
    - Loss of consciousness
    
    Args:
        query (str): User's question
    
    Returns:
        dict: {
            "is_emergency": bool,
            "emergency_types": List[str],
            "emergency_response": str (if emergency detected)
        }
    """
    query_lower = query.lower()
    
    emergency_patterns = {
        'severe_hyperglycemia': [
            r'blood sugar (over|above|more than) (\d{3,})',
            r'glucose.*?(\d{3,})',
            r'(\d{3,}).*?(blood sugar|glucose)'
        ],
        'severe_hypoglycemia': [
            r'blood sugar (under|below|less than) (40|30|20)',
            r'glucose.*?([1-3]\d)',
            r'(unconscious|passing out|fainted).*?(diabetes|sugar)'
        ],
        'dka_symptoms': [
            r'fruity.*(breath|smell)',
            r'(vomiting|nausea).*(diabetes|sugar)',
            r'(rapid|fast) breathing.*(diabetes|sugar)',
            r'(diabetic ketoacidosis|dka)'
        ],
        'cardiac': [
            r'chest pain.*(diabetes|diabetic)',
            r'heart attack.*(diabetes|sugar)',
            r'difficulty breathing.*(diabetes|diabetic)'
        ],
        'severe_confusion': [
            r'(confused|disoriented|delirious).*(diabetes|sugar)',
            r'can\'?t (think|focus).*?(diabetes|sugar)'
        ]
    }
    
    detected_emergencies = []
    
    for emergency_type, patterns in emergency_patterns.items():
        for pattern in patterns:
            if re.search(pattern, query_lower):
                detected_emergencies.append(emergency_type)
                break
    
    if detected_emergencies:
        emergency_response = f"""🚨 **MEDICAL EMERGENCY DETECTED** 🚨

Based on your message, you may be experiencing a medical emergency related to diabetes.

**IMMEDIATE ACTIONS REQUIRED:**
1. **CALL 911** or your local emergency number immediately
2. If you have a glucagon kit (for low blood sugar), use it now
3. Do NOT drive yourself - wait for emergency services
4. Stay with someone if possible
5. Have your medications and medical information ready

**Why this is urgent:**
{_format_emergency_reasons(detected_emergencies)}

**This is an AI assistant. This is NOT a substitute for professional medical care.**
**Please seek immediate medical attention.**

National Diabetes Emergency Hotline: 1-800-DIABETES (1-800-342-2383)
"""
        
        return {
            "is_emergency": True,
            "emergency_types": detected_emergencies,
            "emergency_response": emergency_response
        }
    
    return {
        "is_emergency": False,
        "emergency_types": [],
        "emergency_response": None
    }


def _format_emergency_reasons(emergency_types: List[str]) -> str:
    """Format emergency explanations for user."""
    explanations = {
        'severe_hyperglycemia': "- Blood sugar over 400 mg/dL can lead to diabetic ketoacidosis (DKA), a life-threatening condition",
        'severe_hypoglycemia': "- Blood sugar under 40 mg/dL can cause seizures, loss of consciousness, or death",
        'dka_symptoms': "- Diabetic ketoacidosis is a medical emergency requiring immediate hospitalization",
        'cardiac': "- Diabetes increases heart attack risk; chest pain requires immediate evaluation",
        'severe_confusion': "- Severe confusion with diabetes may indicate dangerous blood sugar levels"
    }
    return "\n".join([explanations.get(et, f"- {et}") for et in emergency_types])


@tool
def check_medication_safety(medications: List[str], query: str) -> Dict:
    """Checks for potential medication interactions or contraindications based on
    patient's medication list and their current question.
    
    Args:
        medications (List[str]): Patient's current medications
        query (str): User's question
    
    Returns:
        dict: {
            "safety_warnings": List[str],
            "has_concerns": bool
        }
    """
    if not medications:
        return {
            "safety_warnings": [],
            "has_concerns": False
        }
    
    query_lower = query.lower()
    
    # Common diabetes medication interaction database
    # In production, this would be a comprehensive database
    interaction_db = {
        'metformin': {
            'contraindications': ['kidney disease', 'renal failure', 'dialysis', 'contrast dye', 'iodine'],
            'interactions': ['alcohol', 'excessive alcohol', 'diuretic'],
            'warnings': 'Metformin should be stopped before surgery or contrast imaging procedures.'
        },
        'insulin': {
            'contraindications': ['hypoglycemia', 'low blood sugar'],
            'interactions': ['beta blocker', 'propranolol', 'ace inhibitor'],
            'warnings': 'Insulin dosing must be carefully managed to avoid severe hypoglycemia.'
        },
        'glipizide': {
            'contraindications': ['sulfa allergy'],
            'interactions': ['warfarin', 'coumadin', 'nsaid', 'ibuprofen'],
            'warnings': 'Sulfonylureas like glipizide can cause hypoglycemia, especially with missed meals.'
        },
        'glyburide': {
            'contraindications': ['liver disease', 'sulfa allergy'],
            'interactions': ['warfarin', 'coumadin', 'nsaid'],
            'warnings': 'Glyburide has higher hypoglycemia risk than other sulfonylureas.'
        },
        'sitagliptin': {
            'contraindications': ['pancreatitis', 'kidney disease'],
            'interactions': ['digoxin'],
            'warnings': 'DPP-4 inhibitors rarely may increase pancreatitis risk.'
        }
    }
    
    safety_warnings = []
    
    for medication in medications:
        med_lower = medication.lower()
        
        # Check each known medication
        for known_med, info in interaction_db.items():
            if known_med in med_lower:
                # Check for contraindications in query
                for contraindication in info['contraindications']:
                    if contraindication in query_lower:
                        safety_warnings.append(
                            f"⚠️ **WARNING**: {medication} may not be safe with {contraindication}. "
                            f"Please consult your doctor before making any changes to your medications."
                        )
                
                # Check for drug interactions
                for interaction in info['interactions']:
                    if interaction in query_lower:
                        safety_warnings.append(
                            f"⚠️ **INTERACTION ALERT**: {medication} may interact with {interaction}. "
                            f"Discuss this with your pharmacist or doctor."
                        )
                
                # Add general warnings if relevant keywords found
                warning_keywords = ['side effect', 'problem', 'issue', 'concern']
                if any(kw in query_lower for kw in warning_keywords):
                    safety_warnings.append(
                        f"ℹ️ **Note**: {info['warnings']}"
                    )
    
    return {
        "safety_warnings": safety_warnings,
        "has_concerns": len(safety_warnings) > 0
    }
