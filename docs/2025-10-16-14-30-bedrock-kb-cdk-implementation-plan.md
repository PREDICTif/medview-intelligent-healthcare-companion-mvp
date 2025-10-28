# Bedrock Knowledge Base CDK Implementation Plan
## Adding Diabetes KB to StrandsChat Stack

**Project:** Intelligent Healthcare Companion MVP  
**Client:** MedviewConnect  
**Stack:** StrandsChat (cdk/lib/strands-chat-stack.ts)  
**Document Version:** 1.0  
**Date:** October 16, 2025  
**Author:** Development Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architectural Decision](#architectural-decision)
3. [Current State Analysis](#current-state-analysis)
4. [Technical Design](#technical-design)
5. [Implementation Steps](#implementation-steps)
6. [Testing Strategy](#testing-strategy)
7. [Rollback Plan](#rollback-plan)
8. [Cost Impact](#cost-impact)

---

## Executive Summary

### Problem Statement
The diabetes corrective RAG implementation (completed October 16, 2025) currently requires **manual creation** of the Bedrock Knowledge Base via AWS Console. This creates:
- Manual deployment steps that are error-prone
- No version control for KB infrastructure
- Inconsistent configuration across environments
- Difficulty in disaster recovery

### Solution
Add Bedrock Knowledge Base resources to the **`StrandsChat` CDK stack** to enable:
- ✅ Fully automated infrastructure deployment
- ✅ Version-controlled KB configuration
- ✅ Repeatable deployments across environments
- ✅ Integrated with existing application stack

### Why StrandsChat Stack?
After architectural analysis of three options:
1. ✅ **StrandsChat** - Application resource, co-located with Lambda consumer
2. ❌ MihcStack - Wrong abstraction (KB ≠ patient database)
3. ❌ StrandsChatWaf - Wrong responsibility (security only)

**Decision:** StrandsChat is the correct home because:
- Lambda function that uses KB already lives there
- KB is application-specific, not shared platform infrastructure
- Follows existing pattern (DynamoDB, S3 buckets already in this stack)
- Simpler deployment (single atomic unit)

### Timeline
- **Planning**: October 16, 2025 (this document)
- **Implementation**: 4-6 hours
- **Testing**: 2-3 hours
- **Deployment**: 1 hour
- **Total**: ~1 day

### Key Infrastructure Note

**Existing S3 Bucket:** The bucket `mihc-diabetes-kb` already exists with diabetes content:
```
s3://mihc-diabetes-kb/
├── diabetes-webmd/          ← Data source for Knowledge Base
├── diabetes-webmd-weekly/   ← Weekly scraper output
└── diabetes-scraper/        ← Scraper metadata/tracking
```

**About S3 and VPCs:**
- S3 buckets are regional services, not VPC resources
- `MihcStack` has a VPC, but S3 exists outside it
- Bedrock KB accesses S3 via public endpoint (required for service integration)

---

## Architectural Decision

### Option Comparison Table

| Criteria | StrandsChat ✅ | MihcStack | StrandsChatWaf |
|----------|----------------|-----------|----------------|
| **Co-location with consumer** | ✅ Lambda is here | ❌ Lambda elsewhere | ❌ Lambda elsewhere |
| **Single deployment unit** | ✅ Atomic | ❌ Cross-stack | ❌ Cross-stack |
| **Appropriate abstraction** | ✅ App resource | ❌ Platform resource | ❌ Security resource |
| **Follows existing pattern** | ✅ DynamoDB, S3 here | ⚠️ Database focus | ❌ WAF only |
| **Simplicity** | ✅ Direct reference | ❌ Cross-stack props | ❌ Wrong layer |
| **Data classification match** | ✅ Public medical knowledge | ❌ Patient PHI | ❌ N/A |

### Architectural Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    StrandsChat Stack                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Cognito    │  │  CloudFront  │  │      S3      │     │
│  │ (Auth Users) │  │     (CDN)    │  │  (Storage)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  🆕 ┌──────────────┐  │
│  │   DynamoDB   │  │    Lambda    │────▶│  Bedrock KB  │  │
│  │(Chat History)│  │  (API/Agent) │     │  (Diabetes)  │  │
│  └──────────────┘  └──────────────┘     └──────────────┘  │
│                           │                     │           │
│                           └─────────────────────┘           │
│                         Direct Reference                    │
│                         (No Cross-Stack)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Current State Analysis

### Existing StrandsChat Resources (Relevant)

```typescript
// Current resources in strands-chat-stack.ts (line ~113-150)

const fileBucket = new Bucket(this, 'FileBucket', bucketCommonProps);
// ↑ User uploads for chat

const table = new Table(this, 'Table', {
  partitionKey: { name: 'queryId', type: AttributeType.STRING },
  sortKey: { name: 'orderBy', type: AttributeType.NUMBER },
  billingMode: BillingMode.PAY_PER_REQUEST,
});
// ↑ Chat history storage

const handler = new DockerImageFunction(this, 'ApiHandler', {
  // ... ~200 lines of configuration
  environment: {
    BUCKET: fileBucket.bucketName,
    TABLE: table.tableName,
    PARAMETER: JSON.stringify(props.parameter),
    TAVILY_API_KEY: tavilyApiKey ?? '',
    // 🆕 DIABETES_KB_ID will go here
  },
});
```

### Current Parameter Schema (parameter.types.ts)

```typescript
export const ParameterSchema = z.object({
  appRegion: z.string(),
  models: z.array(ModelSchema),
  tavilyApiKeySecretArn: z.union([z.null(), z.string()]),
  openWeatherApiKeySecretArn: z.union([z.null(), z.string()]),
  novaCanvasRegion: z.string(),
  createTitleModel: ModelSchema.omit({ displayName: true }),
  agentCoreRegion: z.string(),
  provisionedConcurrency: z.number(),
  // 🆕 Need to add diabetesKnowledgeBaseId field
});
```

### Current Lambda IAM Permissions

```typescript
// Lambda already has extensive Bedrock permissions (line ~200-210)
handler.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'bedrock:InvokeModel',
      'bedrock:InvokeModelWithResponseStream',
      // 🆕 Need to add: 'bedrock:Retrieve', 'bedrock:RetrieveAndGenerate'
    ],
    resources: ['*'],
  })
);
```

---

## Technical Design

### Architecture Components

#### 1. S3 Bucket for KB Data Source

**IMPORTANT:** The bucket `mihc-diabetes-kb` **already exists** and contains diabetes content.

```typescript
// Reference existing S3 bucket (created outside CDK)
const diabetesKnowledgeBucket = Bucket.fromBucketName(
  this,
  'DiabetesKnowledgeBucket',
  'mihc-diabetes-kb'
);

// Note: This bucket already exists with the following structure:
// s3://mihc-diabetes-kb/
//   ├── diabetes-webmd/          ← Data source for KB
//   ├── diabetes-webmd-weekly/   ← Weekly scraper output
//   └── diabetes-scraper/        ← Scraper metadata
```

**Why not create a new bucket?**
- The diabetes scraper (`kb/data-ingestion/web-2-s3/`) is already configured to use `mihc-diabetes-kb`
- Content already exists at `s3://mihc-diabetes-kb/diabetes-webmd/`
- Reusing existing infrastructure reduces complexity

**About S3 and VPCs:**
- ❌ S3 buckets are **NOT created "in a VPC"** - they are regional services
- ✅ S3 can be accessed **from within a VPC** using VPC Gateway Endpoints (recommended)
- The `MihcStack` has a VPC, but we'll access S3 via public endpoint (Bedrock KB requires this)

#### 2. OpenSearch Serverless Collection (Vector Store)

```typescript
// Vector database for embeddings
const vectorCollection = new opensearchserverless.CfnCollection(
  this,
  'DiabetesVectorCollection',
  {
    name: 'diabetes-kb-vectors',
    type: 'VECTORSEARCH',
    description: 'Vector store for diabetes medical knowledge base',
  }
);

// Encryption policy
const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(
  this,
  'VectorEncryptionPolicy',
  {
    name: 'diabetes-kb-encryption',
    type: 'encryption',
    policy: JSON.stringify({
      Rules: [
        {
          ResourceType: 'collection',
          Resource: [`collection/${vectorCollection.name}`],
        },
      ],
      AWSOwnedKey: true,
    }),
  }
);

// Network policy (VPC access if needed)
const networkPolicy = new opensearchserverless.CfnSecurityPolicy(
  this,
  'VectorNetworkPolicy',
  {
    name: 'diabetes-kb-network',
    type: 'network',
    policy: JSON.stringify([
      {
        Rules: [
          {
            ResourceType: 'collection',
            Resource: [`collection/${vectorCollection.name}`],
          },
        ],
        AllowFromPublic: true, // or VPC endpoint
      },
    ]),
  }
);

// Data access policy
const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(
  this,
  'VectorDataAccessPolicy',
  {
    name: 'diabetes-kb-access',
    type: 'data',
    policy: JSON.stringify([
      {
        Rules: [
          {
            ResourceType: 'collection',
            Resource: [`collection/${vectorCollection.name}`],
            Permission: ['aoss:*'],
          },
          {
            ResourceType: 'index',
            Resource: [`index/${vectorCollection.name}/*`],
            Permission: ['aoss:*'],
          },
        ],
        Principal: [kbRole.roleArn, handler.role!.roleArn],
      },
    ]),
  }
);

vectorCollection.addDependency(encryptionPolicy);
vectorCollection.addDependency(networkPolicy);
```

#### 3. IAM Role for Bedrock Knowledge Base

```typescript
const kbRole = new iam.Role(this, 'DiabetesKBRole', {
  assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
  description: 'IAM role for Bedrock Knowledge Base to access S3 and OpenSearch',
  inlinePolicies: {
    BedrockKBPolicy: new iam.PolicyDocument({
      statements: [
        // S3 access
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['s3:GetObject', 's3:ListBucket'],
          resources: [
            diabetesKnowledgeBucket.bucketArn,
            `${diabetesKnowledgeBucket.bucketArn}/*`,
          ],
        }),
        // Bedrock model access for embeddings
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['bedrock:InvokeModel'],
          resources: [
            `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
          ],
        }),
        // OpenSearch Serverless access
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['aoss:APIAccessAll'],
          resources: [vectorCollection.attrArn],
        }),
      ],
    }),
  },
});
```

#### 4. Bedrock Knowledge Base

```typescript
const diabetesKnowledgeBase = new bedrock.CfnKnowledgeBase(
  this,
  'DiabetesKnowledgeBase',
  {
    name: 'diabetes-medical-knowledge',
    description: 'Medical knowledge base for diabetes care and management',
    roleArn: kbRole.roleArn,
    knowledgeBaseConfiguration: {
      type: 'VECTOR',
      vectorKnowledgeBaseConfiguration: {
        embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/amazon.titan-embed-text-v2:0`,
        embeddingModelConfiguration: {
          bedrockEmbeddingModelConfiguration: {
            dimensions: 1024, // Titan v2 dimensions
          },
        },
      },
    },
    storageConfiguration: {
      type: 'OPENSEARCH_SERVERLESS',
      opensearchServerlessConfiguration: {
        collectionArn: vectorCollection.attrArn,
        vectorIndexName: 'diabetes-medical-index',
        fieldMapping: {
          vectorField: 'embedding',
          textField: 'content',
          metadataField: 'metadata',
        },
      },
    },
  }
);

diabetesKnowledgeBase.addDependency(vectorCollection);
diabetesKnowledgeBase.addDependency(dataAccessPolicy);
```

#### 5. Bedrock Data Source

```typescript
const diabetesDataSource = new bedrock.CfnDataSource(
  this,
  'DiabetesDataSource',
  {
    name: 'diabetes-webmd-content',
    description: 'WebMD diabetes articles and clinical guidelines',
    knowledgeBaseId: diabetesKnowledgeBase.attrKnowledgeBaseId,
    dataSourceConfiguration: {
      type: 'S3',
      s3Configuration: {
        bucketArn: diabetesKnowledgeBucket.bucketArn,
        inclusionPrefixes: ['diabetes-webmd/'], // ✅ Correct path
      },
    },
    vectorIngestionConfiguration: {
      chunkingConfiguration: {
        chunkingStrategy: 'FIXED_SIZE',
        fixedSizeChunkingConfiguration: {
          maxTokens: 300,
          overlapPercentage: 20,
        },
      },
    },
  }
);
```

#### 6. Lambda Integration

```typescript
// Add KB ID to Lambda environment
const handler = new DockerImageFunction(this, 'ApiHandler', {
  // ... existing config ...
  environment: {
    // ... existing env vars ...
    DIABETES_KB_ID: diabetesKnowledgeBase.attrKnowledgeBaseId,
    DIABETES_KB_MIN_SCORE: '0.5',
    BEDROCK_EVAL_MODEL_ID: 'us.anthropic.claude-3-7-sonnet-20250219-v1:0',
  },
});

// Grant Lambda permission to use KB
handler.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: [
      'bedrock:Retrieve',
      'bedrock:RetrieveAndGenerate',
      'bedrock:InvokeModel', // For RAGAS evaluation
    ],
    resources: [
      diabetesKnowledgeBase.attrKnowledgeBaseArn,
      `arn:aws:bedrock:${this.region}::foundation-model/*`, // All models
    ],
  })
);
```

#### 7. CDK Outputs

```typescript
// Export KB ID for reference and testing
new cdk.CfnOutput(this, 'DiabetesKnowledgeBaseId', {
  value: diabetesKnowledgeBase.attrKnowledgeBaseId,
  description: 'Bedrock Knowledge Base ID for diabetes medical knowledge',
  exportName: 'DiabetesKBId',
});

new cdk.CfnOutput(this, 'DiabetesKnowledgeBucketName', {
  value: diabetesKnowledgeBucket.bucketName,
  description: 'S3 bucket for diabetes knowledge base content',
  exportName: 'DiabetesKBBucket',
});

new cdk.CfnOutput(this, 'DiabetesDataSourceId', {
  value: diabetesDataSource.attrDataSourceId,
  description: 'Data source ID for triggering KB sync',
  exportName: 'DiabetesKBDataSource',
});
```

---

## Implementation Steps

### Phase 1: CDK Infrastructure (3-4 hours)

#### Step 1.1: Update Parameter Types
```bash
# File: cdk/parameter.types.ts
# Add diabetes KB configuration to schema
```

```typescript
export const ParameterSchema = z.object({
  // ... existing fields ...
  
  // 🆕 Diabetes Knowledge Base configuration
  diabetesKB: z.object({
    enabled: z.boolean().default(true),
    bucketName: z.string().optional(),
    minRelevanceScore: z.number().min(0).max(1).default(0.5),
    chunkingMaxTokens: z.number().default(300),
    chunkingOverlapPercent: z.number().min(0).max(100).default(20),
  }).optional(),
});
```

#### Step 1.2: Update Parameters
```bash
# File: cdk/parameter.ts
# Add diabetes KB configuration
```

```typescript
export const parameter: Parameter = {
  // ... existing config ...
  
  diabetesKB: {
    enabled: true,
    minRelevanceScore: 0.5,
    chunkingMaxTokens: 300,
    chunkingOverlapPercent: 20,
  },
};
```

#### Step 1.3: Add Required CDK Imports
```bash
# File: cdk/lib/strands-chat-stack.ts (top)
```

```typescript
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
```

#### Step 1.4: Create KB Infrastructure Function
```bash
# File: cdk/lib/strands-chat-stack.ts
# Add after existing resource creation (~line 150)
```

```typescript
private createDiabetesKnowledgeBase(
  props: StrandsChatStackProps,
  handler: DockerImageFunction
) {
  if (!props.parameter.diabetesKB?.enabled) {
    return null; // KB disabled
  }

  // 1. Reference existing S3 Bucket (mihc-diabetes-kb)
  const kbBucket = Bucket.fromBucketName(
    this,
    'DiabetesKnowledgeBucket',
    'mihc-diabetes-kb' // ✅ Existing bucket
  );

  // 2. OpenSearch Serverless Collection
  const vectorCollection = new opensearchserverless.CfnCollection(
    // ... (implementation from Technical Design section)
  );

  // 3. IAM Role
  const kbRole = new iam.Role(/* ... */);

  // 4. Knowledge Base
  const knowledgeBase = new bedrock.CfnKnowledgeBase(/* ... */);

  // 5. Data Source (points to s3://mihc-diabetes-kb/diabetes-webmd/)
  const dataSource = new bedrock.CfnDataSource(/* ... */);

  // 6. Grant Lambda access
  handler.addToRolePolicy(/* ... */);

  // 7. Update Lambda environment
  handler.addEnvironment('DIABETES_KB_ID', knowledgeBase.attrKnowledgeBaseId);
  handler.addEnvironment('DIABETES_KB_MIN_SCORE', 
    props.parameter.diabetesKB.minRelevanceScore.toString()
  );

  // 8. Outputs
  new cdk.CfnOutput(this, 'DiabetesKnowledgeBaseId', {
    value: knowledgeBase.attrKnowledgeBaseId,
  });
  
  new cdk.CfnOutput(this, 'DiabetesKnowledgeBucketName', {
    value: kbBucket.bucketName, // Will output: mihc-diabetes-kb
  });

  return {
    knowledgeBase,
    bucket: kbBucket,
    dataSource,
  };
}
```

#### Step 1.5: Call Function in Constructor
```bash
# File: cdk/lib/strands-chat-stack.ts
# Add after Lambda creation (~line 280)
```

```typescript
constructor(scope: Construct, id: string, props: StrandsChatStackProps) {
  // ... existing resources ...

  // Create Lambda handler
  const handler = new DockerImageFunction(this, 'ApiHandler', {
    // ... existing config ...
  });

  // 🆕 Create Diabetes Knowledge Base
  const diabetesKB = this.createDiabetesKnowledgeBase(props, handler);

  // ... rest of constructor ...
}
```

### Phase 2: Testing (2-3 hours)

#### Step 2.1: Validate CDK Synthesis
```bash
cd /Users/rc/Work/SourceCode/medview-intelligent-healthcare-companion-mvp/cdk

# Test CDK synthesis
npx cdk synth StrandsChat --profile medView

# Should output CloudFormation template with:
# - AWS::S3::Bucket (DiabetesKnowledgeBucket)
# - AWS::OpenSearchServerless::Collection
# - AWS::Bedrock::KnowledgeBase
# - AWS::Bedrock::DataSource
```

#### Step 2.2: Review Generated CloudFormation
```bash
# Check that all resources are generated correctly
npx cdk synth StrandsChat --profile medView > /tmp/strands-chat-synth.yaml

# Search for key resources
grep -A 10 "DiabetesKnowledgeBase" /tmp/strands-chat-synth.yaml
grep -A 10 "DiabetesVectorCollection" /tmp/strands-chat-synth.yaml
grep -A 10 "DiabetesDataSource" /tmp/strands-chat-synth.yaml
```

#### Step 2.3: Diff Against Existing Stack
```bash
# See what will change
npx cdk diff StrandsChat --profile medView

# Expected additions:
# + AWS::S3::Bucket DiabetesKnowledgeBucket
# + AWS::OpenSearchServerless::Collection DiabetesVectorCollection
# + AWS::OpenSearchServerless::SecurityPolicy (x2)
# + AWS::OpenSearchServerless::AccessPolicy
# + AWS::IAM::Role DiabetesKBRole
# + AWS::Bedrock::KnowledgeBase DiabetesKnowledgeBase
# + AWS::Bedrock::DataSource DiabetesDataSource
# ~ AWS::Lambda::Function ApiHandler (environment variables updated)
# ~ AWS::IAM::Policy ApiHandlerPolicy (bedrock permissions added)
```

### Phase 3: Deployment (1 hour)

#### Step 3.1: Deploy to Development
```bash
# Deploy updated stack
npx cdk deploy StrandsChat --profile medView

# Monitor deployment progress
# Expected time: 15-20 minutes (OpenSearch Serverless creation is slow)
```

#### Step 3.2: Verify Resources Created
```bash
# 1. Verify Knowledge Base exists
aws bedrock-agent list-knowledge-bases \
  --region us-east-1 \
  --profile medView

# 2. Get KB ID from stack output
KB_ID=$(aws cloudformation describe-stacks \
  --stack-name StrandsChat \
  --query 'Stacks[0].Outputs[?OutputKey==`DiabetesKnowledgeBaseId`].OutputValue' \
  --output text \
  --profile medView)

echo "Knowledge Base ID: $KB_ID"

# 3. Verify Lambda environment variable
aws lambda get-function-configuration \
  --function-name StrandsChat-ApiHandler \
  --query 'Environment.Variables.DIABETES_KB_ID' \
  --profile medView

# Should output: kb-XXXXXXXXXX (same as $KB_ID)
```

#### Step 3.3: Upload Test Data
```bash
# Bucket already exists: mihc-diabetes-kb
KB_BUCKET="mihc-diabetes-kb"

# Create test document
cat > /tmp/test-diabetes-content.json << 'EOF'
{
  "title": "Type 2 Diabetes Symptoms Test",
  "content": "Type 2 diabetes symptoms include increased thirst, frequent urination, increased hunger, fatigue, blurred vision, slow-healing sores, and frequent infections.",
  "url": "https://test.example.com/diabetes-symptoms",
  "source": "Test",
  "scraped_at": "2025-10-16T14:30:00Z"
}
EOF

# Upload to KB bucket (diabetes-webmd/ prefix, not diabetes-webmd-weekly/)
aws s3 cp /tmp/test-diabetes-content.json \
  s3://$KB_BUCKET/diabetes-webmd/test-content.json \
  --profile medView

# Verify upload
aws s3 ls s3://$KB_BUCKET/diabetes-webmd/ --profile medView

# Trigger ingestion
DATA_SOURCE_ID=$(aws cloudformation describe-stacks \
  --stack-name StrandsChat \
  --query 'Stacks[0].Outputs[?OutputKey==`DiabetesDataSourceId`].OutputValue' \
  --output text \
  --profile medView)

aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID \
  --region us-east-1 \
  --profile medView

# Monitor ingestion job
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID \
  --region us-east-1 \
  --profile medView
```

#### Step 3.4: Test Retrieval
```bash
# Test KB retrieval via AWS CLI
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query text="What are the symptoms of type 2 diabetes?" \
  --region us-east-1 \
  --profile medView

# Should return test document with similarity score
```

---

## Testing Strategy

### Unit Tests (CDK)

```typescript
// test/strands-chat-stack.test.ts

import { App } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { StrandsChatStack } from '../lib/strands-chat-stack';

describe('DiabetesKnowledgeBase', () => {
  test('Creates Knowledge Base when enabled', () => {
    const app = new App();
    const stack = new StrandsChatStack(app, 'TestStack', {
      webAclArn: 'arn:aws:wafv2:us-east-1:123456789012:global/webacl/test',
      parameter: {
        // ... required params ...
        diabetesKB: { enabled: true, minRelevanceScore: 0.5 },
      },
    });

    const template = Template.fromStack(stack);

    // Assert KB exists
    template.hasResourceProperties('AWS::Bedrock::KnowledgeBase', {
      Name: 'diabetes-medical-knowledge',
    });

    // Assert S3 bucket exists
    template.resourceCountIs('AWS::S3::Bucket', 4); // +1 for KB bucket

    // Assert Lambda has KB environment variable
    template.hasResourceProperties('AWS::Lambda::Function', {
      Environment: {
        Variables: {
          DIABETES_KB_ID: { 'Fn::GetAtt': ['DiabetesKnowledgeBase', 'KnowledgeBaseId'] },
        },
      },
    });
  });

  test('Skips KB when disabled', () => {
    const app = new App();
    const stack = new StrandsChatStack(app, 'TestStack', {
      webAclArn: 'arn:aws:wafv2:us-east-1:123456789012:global/webacl/test',
      parameter: {
        // ... required params ...
        diabetesKB: { enabled: false },
      },
    });

    const template = Template.fromStack(stack);

    // Assert no KB created
    template.resourceCountIs('AWS::Bedrock::KnowledgeBase', 0);
  });
});
```

### Integration Tests

```python
# tests/integration/test_kb_deployment.py

import boto3
import pytest
import json

@pytest.fixture
def kb_id():
    """Get KB ID from CloudFormation output"""
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    response = cfn.describe_stacks(StackName='StrandsChat')
    outputs = response['Stacks'][0]['Outputs']
    kb_output = next(o for o in outputs if o['OutputKey'] == 'DiabetesKnowledgeBaseId')
    return kb_output['OutputValue']

def test_kb_exists(kb_id):
    """Verify KB was created successfully"""
    bedrock = boto3.client('bedrock-agent', region_name='us-east-1')
    response = bedrock.get_knowledge_base(knowledgeBaseId=kb_id)
    assert response['knowledgeBase']['name'] == 'diabetes-medical-knowledge'

def test_kb_retrieval(kb_id):
    """Test retrieving content from KB"""
    bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')
    
    response = bedrock_runtime.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={'text': 'What are diabetes symptoms?'}
    )
    
    # Should return results
    assert 'retrievalResults' in response
    assert len(response['retrievalResults']) > 0
    
    # Check result structure
    result = response['retrievalResults'][0]
    assert 'content' in result
    assert 'score' in result
    assert result['score'] > 0.0

def test_lambda_has_kb_env_var():
    """Verify Lambda has KB ID environment variable"""
    lambda_client = boto3.client('lambda', region_name='us-east-1')
    response = lambda_client.get_function_configuration(
        FunctionName='StrandsChat-ApiHandler'
    )
    
    env_vars = response['Environment']['Variables']
    assert 'DIABETES_KB_ID' in env_vars
    assert env_vars['DIABETES_KB_ID'].startswith('kb-')
```

### End-to-End Test

```bash
# test_e2e_diabetes_query.sh

#!/bin/bash
set -e

echo "Running E2E test of diabetes corrective RAG..."

# 1. Get API endpoint
API_URL=$(aws cloudformation describe-stacks \
  --stack-name StrandsChat \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text \
  --profile medView)

# 2. Authenticate (get token)
# ... (implementation depends on Cognito setup)

# 3. Send test query
curl -X POST "$API_URL/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the symptoms of type 2 diabetes?",
    "tools": ["diabetes", "reasoning"]
  }' | jq .

# 4. Verify response
# - Should contain diabetes symptoms
# - Should have citations/sources
# - Should NOT trigger emergency detection
# - Should use query_diabetes_knowledge tool

echo "✅ E2E test passed"
```

---

## Rollback Plan

### Scenario 1: Deployment Fails

```bash
# If deployment fails mid-way, CDK will automatically rollback
# No manual intervention needed

# Check rollback status
aws cloudformation describe-stack-events \
  --stack-name StrandsChat \
  --max-items 50 \
  --profile medView | grep -i rollback

# If stack is stuck, manually cancel update
aws cloudformation cancel-update-stack \
  --stack-name StrandsChat \
  --profile medView
```

### Scenario 2: KB Not Working (Post-Deployment)

```bash
# Option A: Disable KB via parameter
# Edit cdk/parameter.ts:
#   diabetesKB: { enabled: false }

# Redeploy
npx cdk deploy StrandsChat --profile medView

# Option B: Revert to previous stack version
aws cloudformation continue-update-rollback \
  --stack-name StrandsChat \
  --profile medView
```

### Scenario 3: Need to Completely Remove KB

```bash
# NOTE: Do NOT delete the S3 bucket (mihc-diabetes-kb) - it's shared!
# The bucket exists outside CDK and contains other data.

# 1. Set enabled: false in parameter.ts
# Edit cdk/parameter.ts:
#   diabetesKB: { enabled: false }

# 2. Redeploy (this will remove KB, OpenSearch, but NOT the S3 bucket)
npx cdk deploy StrandsChat --profile medView

# 3. Optionally clean up KB-specific data
# ONLY if you're sure you want to delete KB ingestion data:
aws s3 rm s3://mihc-diabetes-kb/diabetes-webmd/ --recursive --profile medView

# WARNING: The above will delete diabetes content!
# Consider backing up first:
aws s3 sync s3://mihc-diabetes-kb/diabetes-webmd/ \
  /tmp/diabetes-webmd-backup/ --profile medView
```

### Rollback Validation Checklist

- [ ] Lambda function still works (without KB)
- [ ] Other tools (weather, web search) unaffected
- [ ] Chat history intact
- [ ] No orphaned resources (check AWS Console)
- [ ] CloudWatch logs show no errors

---

## Cost Impact

### New Resources Cost Breakdown

| Resource | Monthly Cost | Reasoning |
|----------|--------------|-----------|
| **OpenSearch Serverless** | $~90/month | ~700 OCU-hours (1 OCU 24/7) |
| **S3 Bucket (KB Data)** | $~0.50/month | ~2 GB storage (1000 articles) |
| **Bedrock KB API** | $~0.10/month | Minimal metadata storage |
| **S3 Requests** | $~0.20/month | Ingestion jobs + retrieval |
| **Data Transfer** | $~0.10/month | Minimal egress |
| **Total** | **~$91/month** | Dominated by OpenSearch |

### Per-Query Costs (Unchanged)

The per-query costs from IMPLEMENTATION_SUMMARY.md remain the same:
- Bedrock (Claude): $13.50 per 1K queries
- RAGAS evaluation: $3.00 per 1K queries
- **KB retrieval: $0.10 per 1K queries** (already estimated)
- Web search: $0.75 per 1K queries (15%)
- Infrastructure: $0.53 per 1K queries

### Cost Optimization

**Option 1: Use OpenSearch Provisioned** (for higher volume)
```typescript
// If queries > 10K/month, provisioned is cheaper
// Replace OpenSearch Serverless with:
const vectorStore = new opensearch.Domain(this, 'DiabetesVectorStore', {
  version: opensearch.EngineVersion.OPENSEARCH_2_11,
  capacity: {
    dataNodes: 2,
    dataNodeInstanceType: 't3.small.search', // ~$30/month each
  },
});
// Monthly: ~$60 (vs $90 serverless)
```

**Option 2: Disable KB for Development**
```typescript
// In parameter.ts for dev environment
diabetesKB: {
  enabled: process.env.ENV === 'production', // Only in prod
}
```

---

## Success Criteria

### Deployment Success

- [ ] CDK deployment completes without errors
- [ ] All CloudFormation resources created (9 new resources)
- [ ] Stack outputs include DiabetesKnowledgeBaseId
- [ ] Lambda environment variable DIABETES_KB_ID is set
- [ ] Lambda has bedrock:Retrieve permissions

### Functional Success

- [ ] KB retrieval returns relevant results for test query
- [ ] Lambda can successfully call query_diabetes_knowledge tool
- [ ] RAGAS check_chunks_relevance evaluates retrieved content
- [ ] End-to-end diabetes query works via API
- [ ] Emergency detection still functions
- [ ] Medication safety checks still function

### Quality Success

- [ ] Unit tests pass (CDK resource assertions)
- [ ] Integration tests pass (KB retrieval)
- [ ] E2E test passes (full diabetes query)
- [ ] No errors in CloudWatch logs
- [ ] Performance: KB retrieval < 500ms (p95)

### Documentation Success

- [ ] IMPLEMENTATION_SUMMARY.md updated with CDK approach
- [ ] CHANGELOG.md includes KB CDK implementation
- [ ] Code comments explain KB configuration
- [ ] CDK outputs documented in README

---

## Next Steps After Implementation

### 1. Populate Knowledge Base
```bash
# Deploy diabetes content scraper
cd kb/data-ingestion/web-2-s3
export S3_BUCKET_NAME=$KB_BUCKET
python deploy_weekly_scraper.py

# Manual scraping run
python invoke.py

# Wait for ingestion (~10-15 minutes)
```

### 2. Configure Data Source Sync
```bash
# Set up automatic sync schedule (weekly)
aws events put-rule \
  --name diabetes-kb-sync-weekly \
  --schedule-expression "rate(7 days)" \
  --profile medView

# Create Lambda to trigger ingestion
# Or manually trigger when new content added
```

### 3. Monitor KB Performance
```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name DiabetesKB-Metrics \
  --dashboard-body file://kb-dashboard.json \
  --profile medView

# Key metrics:
# - Retrieval latency (p50, p95, p99)
# - Relevance scores (RAGAS)
# - Query volume
# - Error rate
```

### 4. Optimize Chunking
```bash
# After initial testing, tune parameters in parameter.ts:
diabetesKB: {
  chunkingMaxTokens: 400, // Increase for more context
  chunkingOverlapPercent: 25, // Increase to reduce missed info
}

# Redeploy
npx cdk deploy StrandsChat --profile medView

# Re-ingest data
aws bedrock-agent start-ingestion-job ...
```

---

## Appendix A: File Changes Summary

### Files to Modify

```
cdk/
├── parameter.types.ts         [MODIFY] Add diabetesKB schema
├── parameter.ts               [MODIFY] Add diabetesKB config
└── lib/
    └── strands-chat-stack.ts  [MODIFY] Add KB resources (~150 lines)

docs/
└── 2025-10-16-14-30-bedrock-kb-cdk-implementation-plan.md  [NEW]

IMPLEMENTATION_SUMMARY.md      [MODIFY] Update deployment steps
CHANGELOG.md                   [MODIFY] Add KB CDK entry
```

### Estimated Line Changes

| File | Lines Added | Lines Modified | Total Impact |
|------|-------------|----------------|--------------|
| parameter.types.ts | +10 | 0 | +10 |
| parameter.ts | +7 | 0 | +7 |
| strands-chat-stack.ts | +170 | +5 | +175 |
| **Total** | **+187** | **+5** | **+192** |

**Note:** Slightly fewer lines than originally estimated because we're referencing an existing S3 bucket (`mihc-diabetes-kb`) instead of creating a new one.

---

## Appendix B: Resource ARN Reference

After deployment, resources will have these ARN patterns:

```
Knowledge Base:
arn:aws:bedrock:us-east-1:584360833890:knowledge-base/kb-XXXXXXXXXXXX

Data Source:
arn:aws:bedrock:us-east-1:584360833890:knowledge-base/kb-XXXXXXXXXXXX/data-source/ds-XXXXXXXXXXXX

OpenSearch Collection:
arn:aws:aoss:us-east-1:584360833890:collection/XXXXXXXXXXXX

S3 Bucket (existing, not created by CDK):
arn:aws:s3:::mihc-diabetes-kb

Data Source Path:
s3://mihc-diabetes-kb/diabetes-webmd/

IAM Role:
arn:aws:iam::584360833890:role/StrandsChat-DiabetesKBRole-XXXXXXXXXXXX
```

---

## Appendix C: Troubleshooting Guide

### Issue: S3 Bucket Not Found

**Error:** `The specified bucket does not exist: mihc-diabetes-kb`

**Root Cause:** The expected bucket doesn't exist in your AWS account

**Solution:**
```bash
# Check if bucket exists
aws s3 ls s3://mihc-diabetes-kb --profile medView

# If bucket doesn't exist, create it manually:
aws s3 mb s3://mihc-diabetes-kb --region us-east-1 --profile medView

# Or use a different existing bucket by updating the code:
# In strands-chat-stack.ts, change 'mihc-diabetes-kb' to your bucket name
```

### Issue: CDK Synth Fails

**Error:** `Cannot find module 'aws-cdk-lib/aws-bedrock'`

**Solution:**
```bash
cd cdk
npm install @aws-cdk/aws-bedrock@latest
# OR update aws-cdk-lib to latest version
npm install aws-cdk-lib@latest
```

### Issue: Deployment Fails - OpenSearch Serverless

**Error:** `CREATE_FAILED: OpenSearchServerless::Collection`

**Root Cause:** Service-linked role missing

**Solution:**
```bash
aws iam create-service-linked-role \
  --aws-service-name observability.aoss.amazonaws.com \
  --profile medView
```

### Issue: KB Created But Retrieval Fails

**Error:** `AccessDeniedException: User is not authorized`

**Root Cause:** Data access policy not applied correctly

**Solution:**
```bash
# Verify access policy exists
aws opensearchserverless get-access-policy \
  --name diabetes-kb-access \
  --type data \
  --profile medView

# If missing, redeploy stack
npx cdk deploy StrandsChat --profile medView
```

### Issue: Lambda Can't Access KB

**Error:** `AccessDenied: bedrock:Retrieve`

**Root Cause:** Lambda role missing permissions

**Solution:**
Check Lambda execution role has:
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:Retrieve",
    "bedrock:RetrieveAndGenerate"
  ],
  "Resource": "arn:aws:bedrock:us-east-1:*:knowledge-base/*"
}
```

---

**Document Status:** ✅ Ready for Implementation  
**Approval Required:** Yes (Architecture review)  
**Estimated Implementation Time:** 1 day  
**Risk Level:** Low (all changes in single stack, easy rollback)

---

*Last Updated: October 16, 2025*  
*Next Review: After successful deployment*

