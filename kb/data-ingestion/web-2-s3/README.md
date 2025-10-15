# Diabetes Content Scraper - Web to S3

This module provides automated web scraping functionality to collect diabetes-related content from WebMD and store it in S3 for knowledge base creation.

## Overview

The system consists of:
- **Lambda Function**: Serverless scraper that runs on a schedule
- **Incremental Scraping**: Tracks processed content to avoid duplicates
- **S3 Storage**: Stores scraped content as JSON files
- **EventBridge Scheduling**: Automated weekly execution

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   EventBridge   │───▶│  Lambda Function │───▶│   S3 Bucket     │
│  (Weekly Cron)  │    │   (Scraper)      │    │ (JSON Content)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │     WebMD        │
                       │   (Data Source)  │
                       └──────────────────┘
```

## Files

### Core Components

| File | Purpose | Description |
|------|---------|-------------|
| `lambda_diabetes_scraper.py` | Lambda Handler | Main AWS Lambda function entry point |
| `diabetes_scraper_scheduler_lambda.py` | Scraping Logic | Core scraping and content processing logic |
| `deploy_weekly_scraper.py` | Deployment | Complete deployment script for Lambda and scheduling |
| `requirements_scraper.txt` | Dependencies | Python packages required for Lambda |
| `invoke.py` | Testing | Manual invocation script for testing |

### Legacy Files

| File | Purpose | Status |
|------|---------|--------|
| `diabetes_scraper_scheduler.py` | Original Scraper | ⚠️ Uses Strands - not Lambda compatible |

## Quick Start

### 1. Prerequisites

```bash
# Set environment variables
export S3_BUCKET_NAME=your-diabetes-bucket
export TAVILY_API_KEY=your-tavily-api-key

# Ensure AWS credentials are configured
aws configure list
```

### 2. Deploy the System

```bash
cd medview-intelligent-healthcare-companion-mvp/kb/data-ingestion/web-2-s3
python deploy_weekly_scraper.py
```

This will:
- ✅ Create IAM role with S3 permissions
- ✅ Package and deploy Lambda function
- ✅ Set up EventBridge weekly schedule
- ✅ Configure all necessary permissions

### 3. Test the Function

```bash
# Manual test
python invoke.py

# Or test via AWS CLI
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{"bucket_name":"your-bucket","max_results_per_query":3}' \
  output.json
```

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `S3_BUCKET_NAME` | Yes | Target S3 bucket for content | `diabetes-knowledge-base` |
| `TAVILY_API_KEY` | Yes | API key for enhanced search | `tvly-xxx...` |

### Lambda Configuration

| Setting | Value | Reason |
|---------|-------|--------|
| Runtime | Python 3.9 | Stable Lambda runtime |
| Memory | 512 MB | Sufficient for web scraping |
| Timeout | 15 minutes | Allows processing multiple articles |
| Architecture | x86_64 | Standard Lambda architecture |

### Search Queries

Default search queries (configurable):
- "diabetes symptoms"
- "diabetes treatment"
- "diabetes diet nutrition"
- "type 1 diabetes"
- "type 2 diabetes"
- "diabetes complications"
- "diabetes prevention"
- "diabetes medication"
- "diabetes blood sugar monitoring"
- "diabetes exercise fitness"

## Data Flow

### 1. Content Discovery
```
EventBridge Trigger → Lambda Function → WebMD Search
```

### 2. Content Processing
```
Search Results → Article Scraping → Content Extraction → Deduplication
```

### 3. Storage
```
Processed Content → S3 JSON Files → Content Tracker Update
```

### 4. Tracking
```
URL Hashes → Content Hashes → Last Run Timestamp → Document Count
```

## Output Format

### S3 Object Structure
```
s3://your-bucket/
├── diabetes-webmd-weekly/
│   ├── 20241014_143022_a1b2c3d4.json
│   ├── 20241014_143045_e5f6g7h8.json
│   └── ...
└── diabetes-scraper/
    └── tracker.json
```

### Content JSON Schema
```json
{
  "title": "Article Title",
  "content": "Full article text content...",
  "url": "https://www.webmd.com/diabetes/...",
  "published_date": "2024-01-15",
  "scraped_at": "2024-10-14T14:30:22.123456",
  "source": "WebMD",
  "content_length": 2847,
  "search_query": "diabetes symptoms"
}
```

### Tracker JSON Schema
```json
{
  "url_hashes": ["hash1", "hash2", "..."],
  "content_hashes": ["hash1", "hash2", "..."],
  "last_run": "2024-10-14T14:30:22.123456",
  "total_documents": 156
}
```

## Monitoring

### CloudWatch Logs
```bash
# View logs
aws logs tail /aws/lambda/diabetes-scraper-weekly --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --filter-pattern "ERROR"
```

### Metrics to Monitor
- **Invocation Count**: Function execution frequency
- **Duration**: Execution time per run
- **Error Rate**: Failed executions
- **S3 Objects Created**: New content added
- **Memory Usage**: Resource utilization

### Success Indicators
```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "results": {
      "new_documents_scraped": 5,
      "updated_documents": 2,
      "skipped_existing": 15,
      "errors_count": 0
    }
  }
}
```

## Troubleshooting

### Common Issues

#### 1. Import Errors
```
Error: No module named 'requests'
```
**Solution**: Redeploy with proper dependencies
```bash
python deploy_weekly_scraper.py
```

#### 2. S3 Permission Errors
```
Error: Access Denied
```
**Solution**: Check IAM role permissions
```bash
aws iam get-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-name DiabetesScraperLambdaRolePolicy
```

#### 3. Timeout Errors
```
Error: Task timed out after 900.00 seconds
```
**Solution**: Reduce `max_results_per_query` or increase timeout

#### 4. Rate Limiting
```
Error: 429 Too Many Requests
```
**Solution**: Increase delays between requests in scraper logic

### Debug Mode

Enable verbose logging by setting environment variable:
```bash
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --environment Variables='{S3_BUCKET_NAME=your-bucket,TAVILY_API_KEY=your-key,DEBUG=true}'
```

## Customization

### Adding New Search Queries

Edit the default queries in `lambda_diabetes_scraper.py`:
```python
search_queries = event.get('search_queries', [
    "diabetes symptoms",
    "your custom query here"
])
```

### Changing Scraping Frequency

Update EventBridge rule:
```bash
aws events put-rule \
  --name diabetes-scraper-weekly-weekly-schedule \
  --schedule-expression "rate(3 days)"  # Every 3 days instead of 7
```

### Custom Content Processing

Modify `scrape_webmd_article()` in `diabetes_scraper_scheduler_lambda.py` to:
- Extract additional metadata
- Apply content filtering
- Add custom formatting

## Security

### IAM Permissions
The Lambda function requires minimal permissions:
- `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on target bucket
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

### Data Privacy
- No personal information is collected
- Only public WebMD articles are scraped
- Content is stored in your private S3 bucket

### Rate Limiting
- Built-in delays between requests (1-2 seconds)
- Respectful scraping practices
- User-Agent headers identify the scraper

## Maintenance

### Regular Tasks
1. **Monitor S3 costs** - Archive old content if needed
2. **Review error logs** - Address any recurring issues
3. **Update search queries** - Keep content relevant
4. **Check content quality** - Verify scraping accuracy

### Updates
To update the scraper:
1. Modify the code files
2. Run `python deploy_weekly_scraper.py`
3. Test with `python invoke.py`

## Cost Estimation

### AWS Costs (Monthly)
- **Lambda**: ~$0.50 (4 weekly runs, 5 min each)
- **S3 Storage**: ~$1.00 (1000 articles, 2KB each)
- **EventBridge**: ~$0.10 (4 weekly triggers)
- **Total**: ~$1.60/month

### Scaling Considerations
- Each run processes ~50-100 articles
- Storage grows ~200KB per week
- Consider S3 lifecycle policies for cost optimization

## Support

For issues or questions:
1. Check CloudWatch logs for error details
2. Review this documentation
3. Test with manual invocation
4. Verify AWS permissions and configuration

---

*Last updated: October 2024*