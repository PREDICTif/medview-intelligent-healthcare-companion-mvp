# Troubleshooting Guide - Diabetes Content Scraper

## Quick Diagnostics

### Health Check Commands
```bash
# Check Lambda function status
aws lambda get-function --function-name diabetes-scraper-weekly --query 'Configuration.State'

# Check recent executions
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --query 'events[*].[timestamp,message]' \
  --output table

# Check S3 bucket contents
aws s3 ls s3://your-bucket/diabetes-webmd-weekly/ --recursive | tail -10

# Test function manually
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{"max_results_per_query":1}' \
  test-output.json && cat test-output.json
```

## Common Issues

### 1. Import/Module Errors

#### Error: `Unable to import module 'lambda_diabetes_scraper'`
**Symptoms:**
```json
{
  "errorMessage": "Unable to import module 'lambda_diabetes_scraper': No module named 'requests'",
  "errorType": "Runtime.ImportModuleError"
}
```

**Causes:**
- Missing dependencies in deployment package
- Incorrect file structure in ZIP
- Platform compatibility issues

**Solutions:**
```bash
# Solution 1: Redeploy with correct dependencies
cd medview-intelligent-healthcare-companion-mvp/kb/data-ingestion/web-2-s3
python deploy_weekly_scraper.py

# Solution 2: Manual package rebuild
mkdir lambda_package
pip install requests beautifulsoup4 python-dotenv \
  -t lambda_package \
  --platform manylinux2014_x86_64 \
  --only-binary=:all:

cp lambda_diabetes_scraper.py lambda_package/
cp diabetes_scraper_scheduler_lambda.py lambda_package/

cd lambda_package && zip -r ../diabetes_scraper_lambda.zip . && cd ..

aws lambda update-function-code \
  --function-name diabetes-scraper-weekly \
  --zip-file fileb://diabetes_scraper_lambda.zip
```

**Verification:**
```bash
# Check package contents
unzip -l diabetes_scraper_lambda.zip | grep -E "(requests|bs4|lambda_diabetes)"
```

#### Error: `No module named 'strands'` or `No module named 'pydantic_core'`
**Symptoms:**
```json
{
  "errorMessage": "Unable to import module 'lambda_diabetes_scraper': No module named 'strands'",
  "errorType": "Runtime.ImportModuleError"
}
```

**Cause:** Using wrong scheduler file (non-Lambda compatible)

**Solution:**
```bash
# Ensure using Lambda-compatible version
grep -n "from.*strands" lambda_diabetes_scraper.py
# Should show: from diabetes_scraper_scheduler_lambda import incremental_scrape_diabetes_webmd

# If not, fix the import
sed -i 's/from diabetes_scraper_scheduler/from diabetes_scraper_scheduler_lambda/' lambda_diabetes_scraper.py

# Redeploy
python deploy_weekly_scraper.py
```

### 2. Permission Errors

#### Error: `Access Denied` (S3)
**Symptoms:**
```json
{
  "errorMessage": "An error occurred (AccessDenied) when calling the PutObject operation: Access Denied",
  "errorType": "ClientError"
}
```

**Diagnosis:**
```bash
# Check IAM role permissions
aws iam get-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-name DiabetesScraperLambdaRolePolicy

# Check bucket policy
aws s3api get-bucket-policy --bucket your-diabetes-bucket
```

**Solutions:**
```bash
# Solution 1: Fix IAM policy
cat > s3-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-diabetes-bucket",
        "arn:aws:s3:::your-diabetes-bucket/*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-name DiabetesScraperLambdaRolePolicy \
  --policy-document file://s3-policy.json

# Solution 2: Test S3 access
aws s3 cp test-file.txt s3://your-diabetes-bucket/test/ --profile lambda-role
```

#### Error: `The role defined for the function cannot be assumed by Lambda`
**Symptoms:**
```
ResourceConflictException: The role defined for the function cannot be assumed by Lambda
```

**Cause:** IAM role trust policy issue or propagation delay

**Solutions:**
```bash
# Solution 1: Wait for IAM propagation
sleep 10

# Solution 2: Check trust policy
aws iam get-role --role-name DiabetesScraperLambdaRole --query 'Role.AssumeRolePolicyDocument'

# Solution 3: Fix trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam update-assume-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-document file://trust-policy.json
```

### 3. Runtime Errors

#### Error: `Task timed out after 900.00 seconds`
**Symptoms:**
```json
{
  "errorMessage": "2024-10-14T14:30:22.123Z Task timed out after 900.00 seconds"
}
```

**Causes:**
- Too many search queries
- Network latency
- Large articles taking too long to process

**Solutions:**
```bash
# Solution 1: Increase timeout
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --timeout 1200  # 20 minutes

# Solution 2: Reduce workload
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{"max_results_per_query":3,"search_queries":["diabetes symptoms","diabetes treatment"]}' \
  output.json

# Solution 3: Monitor execution time
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --filter-pattern "REPORT" \
  --query 'events[*].message' | grep Duration
```

#### Error: `Memory Size: 512 MB Max Memory Used: 510 MB`
**Symptoms:** Near memory limit warnings in logs

**Solutions:**
```bash
# Increase memory allocation
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --memory-size 1024

# Monitor memory usage
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --filter-pattern "Max Memory Used" \
  --query 'events[*].message'
```

### 4. Web Scraping Issues

#### Error: `429 Too Many Requests`
**Symptoms:**
```json
{
  "errorMessage": "HTTPError: 429 Client Error: Too Many Requests"
}
```

**Cause:** Rate limiting by WebMD

**Solutions:**
```python
# Increase delays in diabetes_scraper_scheduler_lambda.py
# Line ~320: time.sleep(2)  # Change to time.sleep(5)
# Line ~280: time.sleep(1)  # Change to time.sleep(3)

# Reduce concurrent requests
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{"max_results_per_query":5}' \
  output.json
```

#### Error: `No articles found` or empty results
**Symptoms:**
```json
{
  "results": {
    "new_documents_found": 0,
    "new_documents_scraped": 0
  }
}
```

**Diagnosis:**
```bash
# Test search manually
python3 -c "
from diabetes_scraper_scheduler_lambda import search_webmd_diabetes
results = search_webmd_diabetes('diabetes symptoms', 3)
print(f'Found {len(results)} results')
for r in results: print(r['url'])
"
```

**Solutions:**
- Check if WebMD changed their HTML structure
- Verify search queries are relevant
- Test with different search terms
- Check network connectivity

### 5. EventBridge Scheduling Issues

#### Error: Function not running on schedule
**Diagnosis:**
```bash
# Check rule status
aws events describe-rule --name diabetes-scraper-weekly-schedule

# Check rule targets
aws events list-targets-by-rule --rule diabetes-scraper-weekly-schedule

# Check recent invocations
aws lambda get-function --function-name diabetes-scraper-weekly \
  --query 'Configuration.LastModified'
```

**Solutions:**
```bash
# Enable rule if disabled
aws events enable-rule --name diabetes-scraper-weekly-schedule

# Fix target configuration
aws events put-targets \
  --rule diabetes-scraper-weekly-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT-ID:function:diabetes-scraper-weekly"

# Add missing permission
aws lambda add-permission \
  --function-name diabetes-scraper-weekly \
  --statement-id diabetes-scraper-weekly-schedule-permission \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com
```

## Debugging Techniques

### 1. Enable Debug Logging
```bash
# Add debug environment variable
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --environment Variables='{S3_BUCKET_NAME=your-bucket,TAVILY_API_KEY=your-key,DEBUG=true}'
```

### 2. Local Testing
```python
# test_local.py
import os
os.environ['S3_BUCKET_NAME'] = 'your-test-bucket'

from lambda_diabetes_scraper import lambda_handler

# Test with minimal payload
event = {
    "max_results_per_query": 2,
    "search_queries": ["diabetes symptoms"]
}

result = lambda_handler(event, None)
print(result)
```

### 3. Step-by-Step Debugging
```python
# debug_scraper.py
from diabetes_scraper_scheduler_lambda import *

# Test search
print("Testing search...")
results = search_webmd_diabetes("diabetes symptoms", 2)
print(f"Found {len(results)} results")

# Test scraping
if results:
    print("Testing scraping...")
    content = scrape_webmd_article(results[0]['url'])
    print(f"Scraped {len(content['content'])} characters")

# Test S3 operations
print("Testing S3...")
tracker = load_content_tracker("your-test-bucket")
print(f"Loaded tracker with {len(tracker.url_hashes)} URLs")
```

### 4. CloudWatch Insights Queries
```sql
-- Find errors in last 24 hours
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20

-- Monitor execution duration
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration), max(@duration), min(@duration) by bin(5m)

-- Track memory usage
fields @timestamp, @maxMemoryUsed
| filter @type = "REPORT"
| sort @timestamp desc
| limit 50
```

## Performance Optimization

### 1. Memory Optimization
```bash
# Monitor memory usage patterns
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --filter-pattern "Max Memory Used" \
  --start-time $(date -d '7 days ago' +%s)000 \
  | grep -o "Max Memory Used: [0-9]* MB" \
  | sort -n | tail -10

# Adjust memory based on usage
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --memory-size 768  # Adjust based on actual usage
```

### 2. Execution Time Optimization
```python
# In diabetes_scraper_scheduler_lambda.py, optimize:

# 1. Reduce search delay
time.sleep(0.5)  # Instead of time.sleep(1)

# 2. Parallel processing (if needed)
from concurrent.futures import ThreadPoolExecutor

def scrape_articles_parallel(urls):
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(scrape_webmd_article, urls))
    return results
```

### 3. Cost Optimization
```bash
# Monitor costs
aws ce get-cost-and-usage \
  --time-period Start=2024-10-01,End=2024-10-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Optimize S3 storage
aws s3api put-bucket-lifecycle-configuration \
  --bucket your-diabetes-bucket \
  --lifecycle-configuration file://lifecycle.json
```

## Monitoring Setup

### 1. CloudWatch Alarms
```bash
# Error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "DiabetesScraper-ErrorRate" \
  --alarm-description "High error rate in diabetes scraper" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=FunctionName,Value=diabetes-scraper-weekly \
  --evaluation-periods 1

# Duration alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "DiabetesScraper-Duration" \
  --alarm-description "Long execution time in diabetes scraper" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 600000 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=diabetes-scraper-weekly \
  --evaluation-periods 2
```

### 2. Custom Metrics
```python
# Add to lambda function for custom metrics
import boto3
cloudwatch = boto3.client('cloudwatch')

def put_custom_metric(metric_name, value, unit='Count'):
    cloudwatch.put_metric_data(
        Namespace='DiabetesScraper',
        MetricData=[
            {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit
            }
        ]
    )

# Usage in scraper
put_custom_metric('DocumentsScraped', result.new_documents_scraped)
put_custom_metric('ErrorCount', len(result.errors))
```

## Recovery Procedures

### 1. Function Recovery
```bash
# Restore from backup/version
aws lambda update-function-code \
  --function-name diabetes-scraper-weekly \
  --zip-file fileb://backup-diabetes_scraper_lambda.zip

# Reset to known good configuration
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --timeout 900 \
  --memory-size 512 \
  --environment Variables='{S3_BUCKET_NAME=your-bucket,TAVILY_API_KEY=your-key}'
```

### 2. Data Recovery
```bash
# Restore S3 data from backup
aws s3 sync s3://backup-bucket/diabetes-webmd-weekly/ s3://your-bucket/diabetes-webmd-weekly/

# Reset content tracker
aws s3 rm s3://your-bucket/diabetes-scraper/tracker.json
```

### 3. Complete Redeployment
```bash
# Clean slate redeployment
cd medview-intelligent-healthcare-companion-mvp/kb/data-ingestion/web-2-s3

# Remove existing resources
aws lambda delete-function --function-name diabetes-scraper-weekly
aws events remove-targets --rule diabetes-scraper-weekly-schedule --ids "1"
aws events delete-rule --name diabetes-scraper-weekly-schedule

# Redeploy
python deploy_weekly_scraper.py
```

## Getting Help

### 1. Log Analysis
```bash
# Get comprehensive logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --start-time $(date -d '1 day ago' +%s)000 \
  --query 'events[*].[timestamp,message]' \
  --output text > scraper-logs.txt
```

### 2. System State Export
```bash
# Export current configuration
aws lambda get-function --function-name diabetes-scraper-weekly > function-config.json
aws events describe-rule --name diabetes-scraper-weekly-schedule > rule-config.json
aws iam get-role --role-name DiabetesScraperLambdaRole > role-config.json
```

### 3. Health Check Script
```bash
#!/bin/bash
# health-check.sh
echo "=== Diabetes Scraper Health Check ==="

echo "1. Lambda Function Status:"
aws lambda get-function --function-name diabetes-scraper-weekly --query 'Configuration.State'

echo "2. Recent Executions:"
aws logs filter-log-events \
  --log-group-name /aws/lambda/diabetes-scraper-weekly \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --query 'length(events)'

echo "3. S3 Content Count:"
aws s3 ls s3://your-bucket/diabetes-webmd-weekly/ --recursive | wc -l

echo "4. EventBridge Rule Status:"
aws events describe-rule --name diabetes-scraper-weekly-schedule --query 'State'

echo "5. Last Successful Run:"
aws s3api head-object --bucket your-bucket --key diabetes-scraper/tracker.json --query 'LastModified'
```

---

*Troubleshooting Guide Version: 1.0*  
*Last Updated: October 2024*