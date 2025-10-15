# Deployment Guide - Diabetes Content Scraper

## Prerequisites

### 1. AWS Account Setup
- AWS CLI installed and configured
- Appropriate IAM permissions for Lambda, S3, EventBridge, and IAM
- S3 bucket created for storing content

### 2. Environment Setup
```bash
# Install Python dependencies
pip install boto3 requests beautifulsoup4 python-dotenv

# Set required environment variables
export S3_BUCKET_NAME=your-diabetes-bucket
export TAVILY_API_KEY=your-tavily-api-key  # Optional but recommended
export AWS_DEFAULT_REGION=us-east-1
```

### 3. Verify AWS Credentials
```bash
aws sts get-caller-identity
aws s3 ls s3://your-diabetes-bucket  # Should not error
```

## Deployment Methods

### Method 1: Automated Deployment (Recommended)

#### Step 1: Navigate to Directory
```bash
cd medview-intelligent-healthcare-companion-mvp/kb/data-ingestion/web-2-s3
```

#### Step 2: Run Deployment Script
```bash
python deploy_weekly_scraper.py
```

This will automatically:
- ✅ Create IAM role with proper permissions
- ✅ Package Lambda function with dependencies
- ✅ Deploy Lambda function
- ✅ Set up EventBridge weekly schedule
- ✅ Configure all necessary permissions

#### Step 3: Verify Deployment
```bash
# Check Lambda function
aws lambda get-function --function-name diabetes-scraper-weekly

# Check EventBridge rule
aws events describe-rule --name diabetes-scraper-weekly-weekly-schedule

# Test the function
python invoke.py
```

### Method 2: Manual Deployment

#### Step 1: Create IAM Role
```bash
# Create trust policy
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

# Create role
aws iam create-role \
  --role-name DiabetesScraperLambdaRole \
  --assume-role-policy-document file://trust-policy.json

# Attach basic Lambda execution policy
aws iam attach-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

#### Step 2: Create Custom Policy
```bash
cat > permissions-policy.json << EOF
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

# Create and attach custom policy
aws iam create-policy \
  --policy-name DiabetesScraperLambdaRolePolicy \
  --policy-document file://permissions-policy.json

aws iam attach-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-arn arn:aws:iam::ACCOUNT-ID:policy/DiabetesScraperLambdaRolePolicy
```

#### Step 3: Package Lambda Function
```bash
# Create package directory
mkdir lambda_package

# Install dependencies
pip install requests beautifulsoup4 python-dotenv \
  -t lambda_package \
  --platform manylinux2014_x86_64 \
  --only-binary=:all:

# Copy function files
cp lambda_diabetes_scraper.py lambda_package/
cp diabetes_scraper_scheduler_lambda.py lambda_package/

# Create deployment package
cd lambda_package
zip -r ../diabetes_scraper_lambda.zip .
cd ..
```

#### Step 4: Create Lambda Function
```bash
aws lambda create-function \
  --function-name diabetes-scraper-weekly \
  --runtime python3.9 \
  --role arn:aws:iam::ACCOUNT-ID:role/DiabetesScraperLambdaRole \
  --handler lambda_diabetes_scraper.lambda_handler \
  --zip-file fileb://diabetes_scraper_lambda.zip \
  --timeout 900 \
  --memory-size 512 \
  --environment Variables='{S3_BUCKET_NAME=your-bucket,TAVILY_API_KEY=your-key}'
```

#### Step 5: Create EventBridge Rule
```bash
# Create rule
aws events put-rule \
  --name diabetes-scraper-weekly-schedule \
  --schedule-expression "rate(7 days)" \
  --description "Weekly diabetes scraper trigger"

# Add Lambda as target
aws events put-targets \
  --rule diabetes-scraper-weekly-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:ACCOUNT-ID:function:diabetes-scraper-weekly"

# Add permission for EventBridge to invoke Lambda
aws lambda add-permission \
  --function-name diabetes-scraper-weekly \
  --statement-id diabetes-scraper-weekly-schedule-permission \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT-ID:rule/diabetes-scraper-weekly-schedule
```

## Configuration

### Environment Variables

Set these in the Lambda function configuration:

| Variable | Value | Description |
|----------|-------|-------------|
| `S3_BUCKET_NAME` | `your-diabetes-bucket` | Target S3 bucket |
| `TAVILY_API_KEY` | `your-api-key` | Optional: Enhanced search |

```bash
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --environment Variables='{S3_BUCKET_NAME=your-bucket,TAVILY_API_KEY=your-key}'
```

### Lambda Settings

| Setting | Recommended Value | Reason |
|---------|------------------|--------|
| Memory | 512 MB | Sufficient for web scraping |
| Timeout | 15 minutes (900s) | Allows processing multiple articles |
| Runtime | Python 3.9 | Stable and supported |

### EventBridge Schedule

| Setting | Value | Description |
|---------|-------|-------------|
| Schedule Expression | `rate(7 days)` | Weekly execution |
| State | `ENABLED` | Active scheduling |

## Verification

### 1. Function Deployment
```bash
# Check function exists
aws lambda get-function --function-name diabetes-scraper-weekly

# Verify configuration
aws lambda get-function-configuration --function-name diabetes-scraper-weekly
```

### 2. Permissions
```bash
# Check IAM role
aws iam get-role --role-name DiabetesScraperLambdaRole

# List attached policies
aws iam list-attached-role-policies --role-name DiabetesScraperLambdaRole
```

### 3. EventBridge Rule
```bash
# Check rule exists
aws events describe-rule --name diabetes-scraper-weekly-schedule

# List targets
aws events list-targets-by-rule --rule diabetes-scraper-weekly-schedule
```

### 4. Test Execution
```bash
# Manual test
aws lambda invoke \
  --function-name diabetes-scraper-weekly \
  --payload '{"max_results_per_query":2}' \
  test-output.json

# Check result
cat test-output.json
```

## Troubleshooting

### Common Deployment Issues

#### 1. Permission Denied
```
Error: User is not authorized to perform: lambda:CreateFunction
```
**Solution**: Ensure your AWS user has Lambda permissions
```bash
aws iam attach-user-policy \
  --user-name your-username \
  --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess
```

#### 2. Role Cannot Be Assumed
```
Error: The role defined for the function cannot be assumed by Lambda
```
**Solution**: Wait 10 seconds after role creation, or check trust policy

#### 3. Package Too Large
```
Error: Request must be smaller than 69905067 bytes
```
**Solution**: Use Lambda layers or optimize dependencies
```bash
# Remove unnecessary files
find lambda_package -name "*.pyc" -delete
find lambda_package -name "__pycache__" -type d -exec rm -rf {} +
```

#### 4. Import Errors
```
Error: Unable to import module 'lambda_diabetes_scraper'
```
**Solution**: Verify file structure and dependencies
```bash
# Check package contents
unzip -l diabetes_scraper_lambda.zip | head -20
```

### Deployment Validation

#### 1. Check CloudWatch Logs
```bash
# View recent logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/diabetes-scraper"

# Tail logs
aws logs tail /aws/lambda/diabetes-scraper-weekly --follow
```

#### 2. Verify S3 Access
```bash
# Test S3 permissions
aws s3 ls s3://your-diabetes-bucket/diabetes-webmd-weekly/
```

#### 3. Monitor Execution
```bash
# Check recent invocations
aws lambda get-function --function-name diabetes-scraper-weekly \
  --query 'Configuration.LastModified'
```

## Updates

### Code Updates
```bash
# Update function code
python deploy_weekly_scraper.py

# Or manually
aws lambda update-function-code \
  --function-name diabetes-scraper-weekly \
  --zip-file fileb://diabetes_scraper_lambda.zip
```

### Configuration Updates
```bash
# Update environment variables
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --environment Variables='{S3_BUCKET_NAME=new-bucket,TAVILY_API_KEY=new-key}'

# Update timeout
aws lambda update-function-configuration \
  --function-name diabetes-scraper-weekly \
  --timeout 1200
```

### Schedule Updates
```bash
# Change to daily
aws events put-rule \
  --name diabetes-scraper-weekly-schedule \
  --schedule-expression "rate(1 day)"

# Disable scheduling
aws events disable-rule --name diabetes-scraper-weekly-schedule
```

## Cleanup

### Remove All Resources
```bash
# Delete Lambda function
aws lambda delete-function --function-name diabetes-scraper-weekly

# Delete EventBridge rule
aws events remove-targets --rule diabetes-scraper-weekly-schedule --ids "1"
aws events delete-rule --name diabetes-scraper-weekly-schedule

# Delete IAM role and policies
aws iam detach-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam detach-role-policy \
  --role-name DiabetesScraperLambdaRole \
  --policy-arn arn:aws:iam::ACCOUNT-ID:policy/DiabetesScraperLambdaRolePolicy

aws iam delete-policy --policy-arn arn:aws:iam::ACCOUNT-ID:policy/DiabetesScraperLambdaRolePolicy
aws iam delete-role --role-name DiabetesScraperLambdaRole

# Clean up local files
rm -f diabetes_scraper_lambda.zip trust-policy.json permissions-policy.json
rm -rf lambda_package
```

## Best Practices

### 1. Security
- Use least-privilege IAM policies
- Enable CloudTrail for audit logging
- Regularly rotate API keys
- Use VPC endpoints for S3 access if needed

### 2. Monitoring
- Set up CloudWatch alarms for errors
- Monitor S3 storage costs
- Track execution duration trends
- Set up SNS notifications for failures

### 3. Cost Optimization
- Use S3 lifecycle policies for old content
- Monitor Lambda execution costs
- Consider Reserved Capacity for predictable workloads
- Optimize memory allocation based on usage

### 4. Reliability
- Test deployments in staging environment
- Use versioning for Lambda functions
- Implement retry logic for transient failures
- Monitor and alert on success rates

---

*Deployment Guide Version: 1.0*  
*Last Updated: October 2024*