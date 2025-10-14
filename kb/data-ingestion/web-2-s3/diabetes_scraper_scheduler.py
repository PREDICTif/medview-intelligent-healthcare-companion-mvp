#!/usr/bin/env python3
"""
Weekly Diabetes WebMD Scraper with Incremental Updates
Tracks existing content and only scrapes new/updated articles
"""

import json
import boto3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
from urllib.parse import urlparse
import hashlib
import time
import os

from strands import Agent, tool
from strands.models import BedrockModel
from pydantic import BaseModel, Field


class ContentTracker(BaseModel):
    """Model for tracking scraped content"""
    url_hashes: Set[str] = Field(default_factory=set, description="Set of URL hashes already processed")
    content_hashes: Set[str] = Field(default_factory=set, description="Set of content hashes already processed")
    last_run: str = Field(description="Timestamp of last successful run")
    total_documents: int = Field(default=0, description="Total documents processed")


class IncrementalScrapingResult(BaseModel):
    """Model for incremental scraping results"""
    new_documents_found: int = Field(description="New documents discovered")
    new_documents_scraped: int = Field(description="New documents successfully scraped")
    updated_documents: int = Field(description="Documents with updated content")
    skipped_existing: int = Field(description="Documents skipped (already exist)")
    s3_objects_created: List[str] = Field(description="New S3 objects created")
    s3_objects_updated: List[str] = Field(description="S3 objects updated")
    errors: List[str] = Field(description="Errors encountered")
    next_run_scheduled: str = Field(description="Next scheduled run time")


# Configure Bedrock model
bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    region_name="us-east-1",
    temperature=0.1,
)

# Initialize AWS clients
s3_client = boto3.client('s3')
events_client = boto3.client('events')
lambda_client = boto3.client('lambda')


@tool
def load_content_tracker(bucket_name: str, tracker_key: str = "diabetes-scraper/tracker.json") -> ContentTracker:
    """
    Load the content tracker from S3 to see what's already been processed
    """
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=tracker_key)
        tracker_data = json.loads(response['Body'].read().decode('utf-8'))
        
        # Convert lists back to sets for efficient lookups
        tracker_data['url_hashes'] = set(tracker_data.get('url_hashes', []))
        tracker_data['content_hashes'] = set(tracker_data.get('content_hashes', []))
        
        return ContentTracker(**tracker_data)
        
    except s3_client.exceptions.NoSuchKey:
        # First run - create new tracker
        return ContentTracker(
            url_hashes=set(),
            content_hashes=set(),
            last_run=datetime.now().isoformat(),
            total_documents=0
        )
    except Exception as e:
        print(f"Error loading tracker: {e}")
        return ContentTracker(
            url_hashes=set(),
            content_hashes=set(),
            last_run=datetime.now().isoformat(),
            total_documents=0
        )


@tool
def save_content_tracker(tracker: ContentTracker, bucket_name: str, tracker_key: str = "diabetes-scraper/tracker.json") -> bool:
    """
    Save the updated content tracker to S3
    """
    try:
        # Convert sets to lists for JSON serialization
        tracker_data = tracker.dict()
        tracker_data['url_hashes'] = list(tracker.url_hashes)
        tracker_data['content_hashes'] = list(tracker.content_hashes)
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=tracker_key,
            Body=json.dumps(tracker_data, indent=2),
            ContentType='application/json'
        )
        return True
        
    except Exception as e:
        print(f"Error saving tracker: {e}")
        return False


@tool
def check_content_freshness(url: str, existing_content_hash: str = None) -> Dict[str, Any]:
    """
    Check if content at URL has changed since last scrape
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # First, try a HEAD request to check Last-Modified header
        head_response = requests.head(url, headers=headers, timeout=10)
        last_modified = head_response.headers.get('Last-Modified')
        
        # If we have existing content hash, do a quick content check
        if existing_content_hash:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get main content
            content_selectors = ['.article-content', '.content-body', '.main-content', 'article', '.article-body']
            content = ""
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(separator='\n', strip=True)
                    break
            
            if not content:
                body = soup.find('body')
                content = body.get_text(separator='\n', strip=True) if body else ""
            
            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            return {
                'url': url,
                'has_changed': current_hash != existing_content_hash,
                'current_hash': current_hash,
                'last_modified': last_modified,
                'content_length': len(content)
            }
        
        return {
            'url': url,
            'has_changed': True,  # Assume changed if no existing hash
            'last_modified': last_modified
        }
        
    except Exception as e:
        return {
            'url': url,
            'error': str(e),
            'has_changed': True  # Assume changed on error to be safe
        }


@tool
def tavily_search_webmd_diabetes_incremental(
    query: str = "diabetes", 
    max_results: int = 10,
    tracker: ContentTracker = None
) -> List[Dict[str, Any]]:
    """
    Search for diabetes content but filter out already processed URLs
    """
    try:
        import os
        from dotenv import load_dotenv

        load_dotenv()
        tavily_api_key = os.getenv('TAVILY_API_KEY')
        
        if not tavily_api_key:
            return [{"error": "TAVILY_API_KEY environment variable not set"}]
        
        url = "https://api.tavily.com/search"
        search_query = f"site:webmd.com {query} diabetes"
        
        payload = {
            "api_key": tavily_api_key,
            "query": search_query,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": True,
            "max_results": max_results,
            "include_domains": ["webmd.com"]
        }
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('results', [])
        
        # Filter results based on tracker
        new_results = []
        for result in results:
            if 'webmd.com' in result.get('url', '').lower():
                url_hash = hashlib.md5(result.get('url', '').encode()).hexdigest()
                
                # Check if we've seen this URL before
                if tracker and url_hash in tracker.url_hashes:
                    # Check if content has changed
                    content = result.get('raw_content', result.get('content', ''))
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    
                    if content_hash not in tracker.content_hashes:
                        # Content has changed, include it
                        result['is_updated'] = True
                        new_results.append(result)
                else:
                    # New URL, include it
                    result['is_new'] = True
                    new_results.append(result)
        
        return new_results
        
    except Exception as e:
        return [{"error": f"Tavily search failed: {str(e)}"}]


@tool
def incremental_scrape_diabetes_webmd(
    bucket_name: str,
    search_queries: List[str] = None,
    max_results_per_query: int = 10,
    s3_prefix: str = "diabetes-webmd",
    force_update: bool = False
) -> IncrementalScrapingResult:
    """
    Incremental scraping that only processes new or updated content
    """
    if search_queries is None:
        search_queries = [
            "diabetes symptoms",
            "diabetes treatment",
            "diabetes diet nutrition",
            "type 1 diabetes",
            "type 2 diabetes",
            "diabetes complications",
            "diabetes prevention",
            "diabetes medication",
            "diabetes blood sugar",
            "diabetes exercise"
        ]
    
    # Load existing tracker
    tracker = load_content_tracker(bucket_name)
    
    new_documents_found = 0
    new_documents_scraped = 0
    updated_documents = 0
    skipped_existing = 0
    s3_objects_created = []
    s3_objects_updated = []
    errors = []
    
    try:
        for query in search_queries:
            print(f"🔍 Searching for new content: {query}")
            
            # Search with incremental filtering
            search_results = tavily_search_webmd_diabetes_incremental(query, max_results_per_query, tracker)
            
            if search_results and isinstance(search_results[0], dict) and 'error' in search_results[0]:
                errors.append(f"Search failed for '{query}': {search_results[0]['error']}")
                continue
            
            new_documents_found += len(search_results)
            
            for result in search_results:
                try:
                    url = result.get('url')
                    if not url:
                        continue
                    
                    url_hash = hashlib.md5(url.encode()).hexdigest()
                    content = result.get('raw_content', result.get('content', ''))
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    
                    # Skip if we've already processed this exact content
                    if not force_update and content_hash in tracker.content_hashes:
                        skipped_existing += 1
                        continue
                    
                    # Prepare document data
                    doc_data = {
                        'url': url,
                        'title': result.get('title', ''),
                        'content': content,
                        'scraped_at': datetime.now().isoformat(),
                        'content_hash': content_hash,
                        'is_update': result.get('is_updated', False),
                        'is_new': result.get('is_new', False)
                    }
                    
                    # Store in S3
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_title = "".join(c for c in doc_data.get('title', 'untitled')[:50] if c.isalnum() or c in (' ', '-', '_')).strip()
                    clean_title = clean_title.replace(' ', '_')
                    
                    object_key = f"{s3_prefix}/{timestamp}_{url_hash[:8]}_{clean_title}.json"
                    
                    # Enhanced document data for S3
                    s3_doc_data = {
                        **doc_data,
                        'metadata': {
                            'source': 'webmd',
                            'topic': 'diabetes',
                            'scraper': 'incremental-tavily-strands-agent',
                            'search_query': query,
                            'is_update': doc_data.get('is_update', False),
                            'is_new': doc_data.get('is_new', False)
                        }
                    }
                    
                    s3_client.put_object(
                        Bucket=bucket_name,
                        Key=object_key,
                        Body=json.dumps(s3_doc_data, indent=2),
                        ContentType='application/json',
                        Metadata={
                            'source-url': url,
                            'content-hash': content_hash,
                            'scraped-at': doc_data['scraped_at']
                        }
                    )
                    
                    # Update tracker
                    tracker.url_hashes.add(url_hash)
                    tracker.content_hashes.add(content_hash)
                    tracker.total_documents += 1
                    
                    if doc_data.get('is_update'):
                        updated_documents += 1
                        s3_objects_updated.append(object_key)
                        print(f"📝 Updated: {url}")
                    else:
                        new_documents_scraped += 1
                        s3_objects_created.append(object_key)
                        print(f"✅ New: {url}")
                    
                    # Rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    errors.append(f"Error processing {result.get('url', 'unknown')}: {str(e)}")
                    continue
        
        # Update tracker with current run info
        tracker.last_run = datetime.now().isoformat()
        save_content_tracker(tracker, bucket_name)
        
        # Calculate next run time (7 days from now)
        next_run = datetime.now() + timedelta(days=7)
        
        return IncrementalScrapingResult(
            new_documents_found=new_documents_found,
            new_documents_scraped=new_documents_scraped,
            updated_documents=updated_documents,
            skipped_existing=skipped_existing,
            s3_objects_created=s3_objects_created,
            s3_objects_updated=s3_objects_updated,
            errors=errors,
            next_run_scheduled=next_run.isoformat()
        )
    
    except Exception as e:
        errors.append(f"General error: {str(e)}")
        return IncrementalScrapingResult(
            new_documents_found=0,
            new_documents_scraped=0,
            updated_documents=0,
            skipped_existing=0,
            s3_objects_created=[],
            s3_objects_updated=[],
            errors=errors,
            next_run_scheduled=(datetime.now() + timedelta(days=7)).isoformat()
        )


@tool
def setup_weekly_schedule(
    bucket_name: str,
    lambda_function_name: str = "diabetes-scraper-weekly",
    schedule_expression: str = "rate(7 days)"
) -> Dict[str, Any]:
    """
    Set up AWS EventBridge rule to run the scraper weekly
    """
    try:
        # Create EventBridge rule
        rule_name = f"{lambda_function_name}-schedule"
        
        events_client.put_rule(
            Name=rule_name,
            ScheduleExpression=schedule_expression,
            Description="Weekly diabetes content scraper from WebMD",
            State='ENABLED'
        )
        
        # Add Lambda function as target
        lambda_arn = f"arn:aws:lambda:{boto3.Session().region_name}:{boto3.client('sts').get_caller_identity()['Account']}:function:{lambda_function_name}"
        
        events_client.put_targets(
            Rule=rule_name,
            Targets=[
                {
                    'Id': '1',
                    'Arn': lambda_arn,
                    'Input': json.dumps({
                        'bucket_name': bucket_name,
                        'scheduled_run': True
                    })
                }
            ]
        )
        
        # Add permission for EventBridge to invoke Lambda
        try:
            lambda_client.add_permission(
                FunctionName=lambda_function_name,
                StatementId=f"{rule_name}-permission",
                Action='lambda:InvokeFunction',
                Principal='events.amazonaws.com',
                SourceArn=f"arn:aws:events:{boto3.Session().region_name}:{boto3.client('sts').get_caller_identity()['Account']}:rule/{rule_name}"
            )
        except lambda_client.exceptions.ResourceConflictException:
            # Permission already exists
            pass
        
        return {
            'success': True,
            'rule_name': rule_name,
            'schedule': schedule_expression,
            'lambda_function': lambda_function_name,
            'next_run': (datetime.now() + timedelta(days=7)).isoformat()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


# Enhanced system prompt
INCREMENTAL_SCRAPER_PROMPT = """You are an intelligent incremental web scraping agent specialized in collecting diabetes-related medical information from WebMD.

Your key capabilities include:
1. **Incremental Processing**: Only scrape new or updated content, avoiding duplicates
2. **Content Tracking**: Maintain a persistent record of processed URLs and content hashes
3. **Change Detection**: Identify when existing articles have been updated
4. **Scheduled Execution**: Support weekly automated runs
5. **Efficient Storage**: Organize content in S3 with proper metadata and versioning

You help users maintain an up-to-date diabetes knowledge base by:
- Tracking what content has already been processed
- Identifying new articles and updates
- Avoiding redundant scraping
- Providing detailed reports on what was found and processed
- Scheduling regular updates

Always provide clear status updates including:
- Number of new documents found vs. already processed
- Content updates detected
- S3 storage locations and organization
- Next scheduled run information
- Any errors or issues encountered
"""

# Create the incremental diabetes scraper agent
incremental_diabetes_scraper = Agent(
    model=bedrock_model,
    system_prompt=INCREMENTAL_SCRAPER_PROMPT,
    tools=[
        load_content_tracker,
        save_content_tracker,
        check_content_freshness,
        tavily_search_webmd_diabetes_incremental,
        incremental_scrape_diabetes_webmd,
        setup_weekly_schedule
    ]
)


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Example usage
    print("🔄 Incremental Diabetes WebMD Scraper")
    print("=" * 50)
    
    bucket_name = os.getenv('S3_BUCKET_NAME', 'diabetes-research-incremental')
    bucket_name = 'mihc-diabetes-kb'

    print(f"Using S3 bucket: {bucket_name}")
    
    # Test the incremental agent
    response = incremental_diabetes_scraper(
        f"""Please run an incremental scrape of diabetes content from WebMD and store new/updated 
        content in S3 bucket '{bucket_name}'. 
        
        Focus on finding:
        - New diabetes articles published since last run
        - Updated content in existing articles
        - Treatment and symptom information
        
        Provide a detailed report of what was found and processed."""
    )
    
    print(response)