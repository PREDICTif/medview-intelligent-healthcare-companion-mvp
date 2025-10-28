# Diabetes Corrective RAG - Implementation Summary

**Date:** October 16, 2025  
**Status:** ✅ Implementation Complete  
**Next Steps:** Deployment & Testing

---

## 🔧 Root Cause Analysis - Deployment Error

**Error:** `No stacks match the name(s) DiabetesKBStack`

**Root Cause:**
- The referenced `DiabetesKBStack` **does not exist** in the CDK codebase
- The implementation plan incorrectly assumed a CDK stack for Knowledge Base deployment
- The actual CDK stacks are: `StrandsChatWaf`, `MihcStack`, `StrandsChat`

**Available Stacks:**
```bash
$ npx cdk list --profile medView
StrandsChatWaf
MihcStack
StrandsChat
```

**Fix:**
1. ✅ **Bedrock Knowledge Base must be created manually** via AWS Console (recommended for MVP)
2. ✅ **Updated deployment instructions** below with correct manual KB creation steps
3. ✅ **Environment variables** set directly in Lambda or via parameter.ts updates
4. 📋 **Future work:** Write `DiabetesKBStack` in `cdk/lib/` to automate KB creation

**What to do now:**
- Skip Step 2 that references `DiabetesKBStack`
- Follow new "Step 2: Create Bedrock Knowledge Base" (manual creation)
- See updated [Deployment Steps](#deployment-steps) below

---

## What Was Implemented

Successfully implemented **Phases 1-3** of the Diabetes Corrective RAG Implementation Plan:

### Phase 1: Core RAG Foundation ✅
- Integrated diabetes knowledge base tools (`query_diabetes_knowledge`, `query_diabetes_with_generation`)
- Tool selection service already configured for diabetes queries
- Frontend UI with diabetes tool icon ready

### Phase 2: Corrective RAG Enhancement ✅
- **RAGAS Evaluation Tool**: `check_chunks_relevance()` using `LLMContextPrecisionWithoutReference`
  - Scores: 0.0-1.0 (threshold: 0.5)
  - Uses Claude 3.7 Sonnet for evaluation
  - Fail-safe: defaults to "relevant" on errors (healthcare safety)
  
- **Medical Web Search**: `medical_web_search()` via Tavily + LangChain
  - Triggered when chunk_relevance_score is "no"
  - Targets authoritative sources (diabetes.org, CDC, NIH, Mayo Clinic, WebMD)
  - Returns formatted results with citations

### Phase 3: Healthcare Safety Features ✅
- **Emergency Detection**: `detect_emergency()`
  - Detects: severe hyperglycemia (>400), hypoglycemia (<40), DKA, cardiac issues
  - Returns immediate emergency response with 911 guidance
  - Must be checked FIRST in workflow
  
- **Medication Safety**: `check_medication_safety()`
  - Checks interactions for: metformin, insulin, glipizide, glyburide, sitagliptin
  - Warns about contraindications and drug interactions
  - Expandable medication database

- **Comprehensive System Prompt**: `generate_diabetes_system_prompt()`
  - 6-step corrective RAG workflow
  - Response guidelines (always cite, never diagnose, recommend consultation)
  - Emergency protocols
  - Examples of good vs bad responses

---

## Files Modified

### Backend (Python)

1. **`api/pyproject.toml`**
   - Added: ragas, langchain, langchain-aws, langchain-community, tavily-python

2. **`api/tools.py`** (+343 lines)
   - `check_chunks_relevance(results: str, question: str) -> Dict`
   - `medical_web_search(query: str) -> str`
   - `detect_emergency(query: str) -> Dict`
   - `check_medication_safety(medications: List[str], query: str) -> Dict`
   - `_format_emergency_reasons(emergency_types: List[str]) -> str`

3. **`api/utils.py`** (+96 lines)
   - `generate_diabetes_system_prompt() -> str`

4. **`api/services/streaming_service.py`**
   - Imported 6 corrective RAG tools
   - Integrated tools when "diabetes" is selected
   - Combined diabetes system prompt with session prompt

### Frontend (TypeScript)
- Already configured (no changes needed):
  - `web/src/components/ToolIcon.tsx` - diabetes heart icon ❤️
  - `web/src/types/index.ts` - diabetes tool type
  - Tool selection hooks already support diabetes

---

## Architecture Overview

```
User Query
    ↓
[Tool Selection] → Detects diabetes topic
    ↓
[Agent with Diabetes System Prompt]
    ↓
Step 1: detect_emergency() ← ALWAYS FIRST
    ↓ (if no emergency)
Step 2: query_diabetes_knowledge() ← Retrieve from KB
    ↓
Step 3: check_chunks_relevance() ← RAGAS evaluation
    ↓
Step 4: medical_web_search() ← If relevance is "no"
    ↓
Step 5: check_medication_safety() ← If medications mentioned
    ↓
Step 6: Generate response with citations
```

---

## Environment Variables Required

Before deployment, set these environment variables:

### Required for Basic Functionality
```bash
# Bedrock Knowledge Base (from deployment output)
DIABETES_KB_ID=kb-XXXXXXXXXXXXX

# AWS Region
AWS_REGION=us-east-1

# Minimum relevance score for KB retrieval
DIABETES_KB_MIN_SCORE=0.5
```

### Required for RAGAS Evaluation
```bash
# Claude model for RAGAS evaluation
BEDROCK_EVAL_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
```

### Required for Web Search
```bash
# Tavily API key (from https://tavily.com)
TAVILY_API_KEY=tvly-XXXXXXXXXXXXX
```

### Already Configured
- `OPENWEATHER_API_KEY` ✅ (already in Secrets Manager)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` ✅ (from CDK)

---

## Deployment Steps

### 1. Install Dependencies
```bash
cd /Users/rc/Work/SourceCode/medview-intelligent-healthcare-companion-mvp/api
uv sync  # Install new dependencies
```

### 2. Create Bedrock Knowledge Base

**⚠️ IMPORTANT: There is NO `DiabetesKBStack` in CDK (yet)**

The Bedrock Knowledge Base must be created manually. You have two options:

#### Option A: Manual Creation (Recommended for MVP)
1. Go to AWS Bedrock Console → Knowledge Bases → Create
2. Configuration:
   - **Name**: `diabetes-knowledge-base`
   - **Embedding Model**: `amazon.titan-embed-text-v2:0`
   - **Data Source**: S3 bucket from diabetes scraper
   - **Chunking**: Default (300 tokens, 20% overlap)
3. Save the Knowledge Base ID (e.g., `kb-ABC123DEF456`)

#### Option B: Create CDK Stack (Future Enhancement)
A `DiabetesKBStack` needs to be written in `cdk/lib/` to automate KB creation.
This is tracked as future work.

**Data Source Setup:**
The diabetes content scraper already exists at `kb/data-ingestion/web-2-s3/`.
Deploy it first to populate S3:
```bash
cd kb/data-ingestion/web-2-s3
export S3_BUCKET_NAME=your-diabetes-bucket
export TAVILY_API_KEY=your-tavily-key
python deploy_weekly_scraper.py
```

### 3. Configure Environment Variables
Since there are no diabetes fields in `parameter.ts` yet, set environment variables directly in Lambda:

```bash
# After creating KB manually, update Lambda environment
aws lambda update-function-configuration \
  --function-name StrandsChat-ApiHandler \
  --environment Variables='{
    DIABETES_KB_ID=kb-ABC123DEF456,
    DIABETES_KB_MIN_SCORE=0.5,
    BEDROCK_EVAL_MODEL_ID=us.anthropic.claude-3-7-sonnet-20250219-v1:0
  }' \
  --profile medView
```

**OR** Update `parameter.ts` (requires schema update in `parameter.types.ts` first):
```typescript
// First add to parameter.types.ts:
diabetesKnowledgeBaseId: z.union([z.null(), z.string()]),
minRelevanceScore: z.number().min(0).max(1).default(0.5),

// Then in parameter.ts:
export const parameter: Parameter = {
  // ... existing config ...
  diabetesKnowledgeBaseId: 'kb-ABC123DEF456',
  minRelevanceScore: 0.5,
};
```

### 4. Create Tavily API Secret
```bash
aws secretsmanager create-secret \
  --name tavily-api-key \
  --secret-string "tvly-YOUR-ACTUAL-KEY" \
  --region us-east-1 \
  --profile medView
```

Update `cdk/parameter.ts`:
```typescript
tavilyApiKeySecretArn: 'arn:aws:secretsmanager:us-east-1:584360833890:secret:tavily-api-key-XXXXXX',
```

### 5. Deploy Application
```bash
cd /Users/rc/Work/SourceCode/medview-intelligent-healthcare-companion-mvp/cdk
npx cdk deploy StrandsChat --profile medView
```

**Available Stacks:**
- `StrandsChatWaf` - WAF configuration
- `MihcStack` - Main infrastructure  
- `StrandsChat` - Application stack (use this one)

### 6. Verify Deployment
```bash
aws lambda get-function-configuration \
  --function-name StrandsChat-ApiHandler \
  --query 'Environment.Variables' \
  --profile medView

# Should show (if using parameter.ts method):
# - DIABETES_KB_ID or PARAMETER containing diabetesKnowledgeBaseId
# - TAVILY_API_KEY
# - BEDROCK_EVAL_MODEL_ID (or in PARAMETER)
```

---

## Testing Checklist

### Phase 1: Basic Retrieval
- [ ] Ask: "What are the symptoms of type 2 diabetes?"
- [ ] Verify: Response includes KB sources
- [ ] Verify: Citations are present

### Phase 2: Corrective RAG
- [ ] Ask: "What diabetes medications were approved by FDA this week?"
  - Should trigger web search (KB won't have recent info)
- [ ] Verify: Web search results included
- [ ] Verify: Both KB and web sources cited

### Phase 3: Safety Features
- [ ] Test emergency: "My blood sugar is 450 and I feel dizzy"
  - Should show 🚨 emergency response with 911 guidance
- [ ] Test medication: "Can I drink alcohol with metformin?"
  - Should show ⚠️ interaction warning
- [ ] Test normal query: "What should I eat for breakfast?"
  - Should work normally (no emergency/warnings)

### Quality Metrics
- [ ] Responses cite sources
- [ ] No medical diagnoses given
- [ ] Recommendations to see doctor when appropriate
- [ ] Emergency detection works (100% recall on test cases)
- [ ] Medication warnings appear when relevant

---

## Cost Estimates

Per 1,000 queries:
- **Bedrock (Claude Sonnet 4)**: $13.50
- **RAGAS (Claude 3.7 Sonnet)**: $3.00
- **Knowledge Base**: $0.10
- **Web Search (15% of queries)**: $0.75
- **Infrastructure**: $0.53
- **Total**: ~$17.88 per 1,000 queries

Monthly at 100K queries: **$1,788**

---

## Troubleshooting

### ❌ "No stacks match the name(s) DiabetesKBStack"
**Root Cause:** `DiabetesKBStack` does not exist in the CDK codebase.

**Solution:** 
- The Bedrock Knowledge Base must be created manually via AWS Console
- OR write a new CDK stack in `cdk/lib/diabetes-kb-stack.ts` (future work)
- See "Step 2: Create Bedrock Knowledge Base" above

**Available stacks:**
```bash
npx cdk list --profile medView
# Output: StrandsChatWaf, MihcStack, StrandsChat
```

### "No module named 'ragas'"
```bash
cd api && uv sync
```

### "DIABETES_KB_ID not found"
**Root Cause:** Environment variable not set in Lambda

**Solution:**
1. Create KB manually in Bedrock Console
2. Set environment variable directly:
   ```bash
   aws lambda update-function-configuration \
     --function-name StrandsChat-ApiHandler \
     --environment Variables='{"DIABETES_KB_ID":"kb-YOUR-ID-HERE"}' \
     --profile medView
   ```
3. OR add to parameter.ts + update schema + redeploy

### "TAVILY_API_KEY not configured"
- Create secret in Secrets Manager
- Update parameter.ts with ARN: `tavilyApiKeySecretArn`
- Redeploy StrandsChat stack

### RAGAS evaluation fails
- Check BEDROCK_EVAL_MODEL_ID is set in Lambda environment
- Verify Claude 3.7 Sonnet access in us-east-1
- Check CloudWatch logs: `/aws/lambda/StrandsChat-ApiHandler`

### Web search not triggering
- Check RAGAS threshold (default 0.5)
- Lower threshold to 0.4 for more searches
- Verify TAVILY_API_KEY is valid
- Test: "What diabetes medications were approved this week?" (should trigger web search)

---

## What's Next (Phase 4)

**Testing & Validation** (Weeks 12-14):

1. **Clinical Validation**
   - Create 100-query test set with expert answers
   - Target: ≥90% accuracy, 100% safety pass rate

2. **Load Testing**
   - Target: 500 concurrent users
   - p95 latency <5 seconds

3. **User Acceptance Testing**
   - 20 target users
   - Target: ≥8/10 satisfaction

4. **Production Readiness**
   - Security audit
   - HIPAA compliance verification
   - Go/no-go decision

---

## Success Criteria

✅ **Phase 1-3 Complete**
- All corrective RAG tools implemented
- System prompt with workflow
- Emergency & medication safety
- Integration with streaming service

📋 **Pending Deployment**
- Dependencies installation (`uv sync`)
- Manual Bedrock Knowledge Base creation (AWS Console)
- Diabetes content scraper deployment (optional, for fresh data)
- Tavily API secret creation
- Lambda environment variables configuration
- CDK deployment to AWS (`npx cdk deploy StrandsChat`)

🧪 **Pending Testing**
- Clinical validation
- Load testing  
- UAT

---

## References

- **Implementation Plan**: `docs/2025-10-15-11-15-diabetes-corrective-rag-implementation-plan.md`
- **Changelog**: `CHANGELOG.md`
- **RAGAS**: https://docs.ragas.io
- **Tavily**: https://docs.tavily.com
- **Bedrock KB**: https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html

---

## Quick Start Guide (Corrected)

For those who just want to get started without reading the full document:

```bash
# 1. Install dependencies
cd api && uv sync

# 2. Create Bedrock Knowledge Base manually in AWS Console
#    - Go to Bedrock → Knowledge Bases → Create
#    - Name: diabetes-knowledge-base
#    - Embedding: amazon.titan-embed-text-v2:0
#    - Save the KB ID (e.g., kb-ABC123)

# 3. Create Tavily secret
aws secretsmanager create-secret \
  --name tavily-api-key \
  --secret-string "tvly-YOUR-KEY" \
  --region us-east-1 \
  --profile medView

# 4. Update parameter.ts with Tavily ARN
# Edit cdk/parameter.ts:
#   tavilyApiKeySecretArn: 'arn:aws:secretsmanager:...:secret:tavily-api-key-XXX'

# 5. Deploy application
cd ../cdk
npx cdk deploy StrandsChat --profile medView

# 6. Set diabetes KB environment variable in Lambda
aws lambda update-function-configuration \
  --function-name StrandsChat-ApiHandler \
  --environment Variables='{"DIABETES_KB_ID":"kb-YOUR-ID"}' \
  --profile medView

# 7. Test!
```

---

**Questions or Issues?**  
- Check [Troubleshooting](#troubleshooting) section above
- Review CloudWatch logs: `/aws/lambda/StrandsChat-ApiHandler`
- Verify available stacks: `npx cdk list --profile medView`

