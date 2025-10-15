# API Documentation - Diabetes Content Scraper

## Lambda Function API

### Function Name
`diabetes-scraper-weekly`

### Runtime
Python 3.9

### Handler
`lambda_diabetes_scraper.lambda_handler`

## Input Schema

### Event Structure
```json
{
  "bucket_name": "string",
  "search_queries": ["string"],
  "max_results_per_query": "integer",
  "s3_prefix": "string",
  "force_update": "boolean",
  "scheduled_run": "boolean"
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bucket_name` | string | No | `mihc-diabetes-kb` | Target S3 bucket name |
| `search_queries` | array | No | See default list | List of search terms |
| `max_results_per_query` | integer | No | `8` | Maximum articles per search query |
| `s3_prefix` | string | No | `diabetes-webmd-weekly` | S3 key prefix for stored content |
| `force_update` | boolean | No | `false` | Force re-scraping of existing content |
| `scheduled_run` | boolean | No | `false` | Indicates if triggered by EventBridge |

### Default Search Queries
```json
[
  "diabetes symptoms",
  "diabetes treatment",
  "diabetes diet nutrition",
  "type 1 diabetes",
  "type 2 diabetes",
  "diabetes complications",
  "diabetes prevention",
  "diabetes medication",
  "diabetes blood sugar monitoring",
  "diabetes exercise fitness"
]
```

## Output Schema

### Success Response
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "execution_time": "integer (milliseconds)",
    "results": {
      "new_documents_found": "integer",
      "new_documents_scraped": "integer",
      "updated_documents": "integer",
      "skipped_existing": "integer",
      "total_s3_objects": "integer",
      "errors_count": "integer",
      "next_run_scheduled": "string (ISO datetime)"
    },
    "details": {
      "s3_objects_created": ["string"],
      "s3_objects_updated": ["string"],
      "errors": ["string"]
    }
  }
}
```

### Error Response
```json
{
  "statusCode": 500,
  "body": {
    "success": false,
    "error": "string",
    "execution_time": "integer (milliseconds)"
  }
}
```

## Core Functions API

### `incremental_scrape_diabetes_webmd()`

Main scraping function that orchestrates the entire process.

```python
def incremental_scrape_diabetes_webmd(
    bucket_name: str,
    search_queries: List[str],
    max_results_per_query: int = 10,
    s3_prefix: str = "diabetes-webmd-weekly",
    force_update: bool = False
) -> IncrementalScrapingResult
```

**Parameters:**
- `bucket_name`: S3 bucket for storing content
- `search_queries`: List of search terms
- `max_results_per_query`: Limit per search query
- `s3_prefix`: S3 key prefix
- `force_update`: Re-scrape existing content

**Returns:** `IncrementalScrapingResult` object

### `search_webmd_diabetes()`

Searches WebMD for diabetes-related content.

```python
def search_webmd_diabetes(
    query: str, 
    max_results: int = 10
) -> List[Dict[str, Any]]
```

**Parameters:**
- `query`: Search term
- `max_results`: Maximum results to return

**Returns:** List of article metadata dictionaries

**Example Output:**
```json
[
  {
    "title": "Diabetes Symptoms: Early Signs",
    "url": "https://www.webmd.com/diabetes/diabetes-symptoms",
    "source": "WebMD",
    "search_query": "diabetes symptoms"
  }
]
```

### `scrape_webmd_article()`

Extracts content from a WebMD article URL.

```python
def scrape_webmd_article(url: str) -> Dict[str, Any]
```

**Parameters:**
- `url`: WebMD article URL

**Returns:** Article content dictionary

**Example Output:**
```json
{
  "title": "Understanding Diabetes Symptoms",
  "content": "Diabetes is a condition that affects...",
  "url": "https://www.webmd.com/diabetes/diabetes-symptoms",
  "published_date": "2024-01-15",
  "scraped_at": "2024-10-14T14:30:22.123456",
  "source": "WebMD",
  "content_length": 2847
}
```

### `load_content_tracker()`

Loads content tracking data from S3.

```python
def load_content_tracker(
    bucket_name: str, 
    tracker_key: str = "diabetes-scraper/tracker.json"
) -> ContentTracker
```

**Parameters:**
- `bucket_name`: S3 bucket name
- `tracker_key`: S3 key for tracker file

**Returns:** `ContentTracker` object

### `save_content_tracker()`

Saves content tracking data to S3.

```python
def save_content_tracker(
    tracker: ContentTracker, 
    bucket_name: str, 
    tracker_key: str = "diabetes-scraper/tracker.json"
)
```

**Parameters:**
- `tracker`: ContentTracker object to save
- `bucket_name`: S3 bucket name
- `tracker_key`: S3 key for tracker file

## Data Models

### ContentTracker

Tracks processed content to avoid duplicates.

```python
class ContentTracker:
    def __init__(self, url_hashes=None, content_hashes=None, last_run=None, total_documents=0):
        self.url_hashes = url_hashes or set()      # Set of processed URL hashes
        self.content_hashes = content_hashes or set()  # Set of processed content hashes
        self.last_run = last_run                   # ISO datetime string
        self.total_documents = total_documents     # Integer count
```

### IncrementalScrapingResult

Results from a scraping operation.

```python
class IncrementalScrapingResult:
    def __init__(self):
        self.new_documents_found = 0        # Documents discovered
        self.new_documents_scraped = 0      # New documents successfully scraped
        self.updated_documents = 0          # Documents with updated content
        self.skipped_existing = 0          # Documents skipped (already exist)
        self.s3_objects_created = []       # List of new S3 keys
        self.s3_objects_updated = []       # List of updated S3 keys
        self.errors = []                   # List of error messages
        self.next_run_scheduled = ""       # ISO datetime string
```

## Utility Functions

### `get_content_hash()`

Generates MD5 hash for content deduplication.

```python
def get_content_hash(content: str) -> str
```

### `get_url_hash()`

Generates MD5 hash for URL deduplication.

```python
def get_url_hash(url: str) -> str
```

## HTTP Headers

### Request Headers (for web scraping)
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
```

### Response Headers (Lambda)
```
Content-Type: application/json
```

## Error Codes

| Status Code | Description | Common Causes |
|-------------|-------------|---------------|
| 200 | Success | Normal operation |
| 400 | Bad Request | Invalid input parameters |
| 403 | Forbidden | S3 permission issues |
| 500 | Internal Server Error | Scraping failures, network issues |
| 504 | Gateway Timeout | Lambda timeout (15 minutes) |

## Rate Limiting

### Built-in Delays
- 1 second between search queries
- 2 seconds between article scraping
- Respectful of WebMD's servers

### Recommended Limits
- Max 10 results per query for production
- Max 10 search queries per run
- Weekly execution frequency

## Authentication

### AWS IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket",
        "arn:aws:s3:::your-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Testing

### Manual Invocation

```bash
# Test with minimal payload
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{"max_results_per_query":2}' \
  output.json

# Test with custom queries
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{
    "bucket_name": "test-bucket",
    "search_queries": ["diabetes symptoms"],
    "max_results_per_query": 3,
    "force_update": true
  }' \
  output.json
```

### Python Testing

```python
import boto3
import json

lambda_client = boto3.client('lambda')

payload = {
    "bucket_name": "test-bucket",
    "search_queries": ["diabetes symptoms"],
    "max_results_per_query": 2
}

response = lambda_client.invoke(
    FunctionName='diabetes-scraper-weekly',
    InvocationType='RequestResponse',
    Payload=json.dumps(payload)
)

result = json.loads(response['Payload'].read())
print(json.dumps(result, indent=2))
```

## Monitoring Endpoints

### CloudWatch Metrics
- `AWS/Lambda/Invocations`
- `AWS/Lambda/Duration`
- `AWS/Lambda/Errors`
- `AWS/Lambda/Throttles`

### Custom Metrics (via logs)
- Documents scraped per run
- S3 objects created
- Error rates by type
- Content quality metrics

---

*API Version: 1.0*  
*Last Updated: October 2024*