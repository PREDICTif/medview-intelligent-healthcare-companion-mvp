# Changelog

All notable changes to the MedView Intelligent Healthcare Companion MVP project will be documented in this file.

## [Unreleased] - 2025-10-16

### Fixed - Frontend Build Error (2:30 PM)

**What Changed:**
- Fixed TypeScript compilation error in web frontend build during CDK deployment
- Added missing `diabetes` state management to `useChatState` hook
- Connected diabetes tool selection to Chat UI component

**Files Modified:**

1. **web/src/hooks/useChatState.ts**
   - Added `hasDiabetes` helper to check for diabetes tool in toolsToUse array
   - Added `diabetes` getter and `setDiabetes` setter following existing pattern for other tools
   - Enables diabetes tool to be toggled in the UI and persisted in session storage

2. **web/src/pages/Chat.tsx**
   - Destructured `diabetes` and `setDiabetes` from `useChatState` hook
   - Passed these props to `ToolsBottomSheet` component to complete the integration

**Why It Matters:**
- Resolves build failure that was blocking CDK deployment of the frontend
- Completes the diabetes tool integration across frontend, backend, and UI layers

---

### Added - Diabetes Corrective RAG Implementation

**What Changed:**
- Implemented Corrective RAG architecture with 4 new specialized tools for diabetes healthcare assistance
- Added RAGAS-based relevance evaluation for retrieved medical knowledge
- Integrated emergency detection and medication safety checking capabilities
- Created comprehensive diabetes-specific system prompt with corrective RAG workflow

**Files Modified:**

1. **api/pyproject.toml**
   - Added dependencies: ragas==0.1.19, langchain==0.2.0, langchain-aws==0.1.0, langchain-community==0.2.0, tavily-python==0.3.0
   - These enable RAGAS evaluation and enhanced web search capabilities

2. **api/tools.py**
   - `check_chunks_relevance()`: RAGAS-based tool using LLMContextPrecisionWithoutReference metric to evaluate if retrieved KB chunks are relevant (0.0-1.0 score, threshold 0.5)
   - `medical_web_search()`: Specialized medical web search using Tavily via langchain, triggered only when chunk_relevance_score is "no"
   - `detect_emergency()`: Pattern-based emergency detection for severe hyperglycemia (>400), hypoglycemia (<40), DKA symptoms, cardiac issues, and confusion
   - `check_medication_safety()`: Medication interaction checker for common diabetes medications (metformin, insulin, glipizide, glyburide, sitagliptin)

3. **api/utils.py**
   - `generate_diabetes_system_prompt()`: Comprehensive system prompt implementing corrective RAG workflow with 6-step process:
     1. Emergency check (always first)
     2. Retrieve from knowledge base
     3. Evaluate relevance with RAGAS
     4. Conditional web search if relevance is low
     5. Medication safety checks if applicable
     6. Generate response with citations
   - Includes response guidelines, examples, and safety protocols

4. **api/services/streaming_service.py**
   - Integrated all 6 corrective RAG tools when "diabetes" tool is selected
   - Combined diabetes system prompt with session system prompt for context
   - Tools now available: query_diabetes_knowledge, query_diabetes_with_generation, check_chunks_relevance, medical_web_search, detect_emergency, check_medication_safety

**Why It Matters:**

This implements Phase 1-3 of the Diabetes Corrective RAG Implementation Plan:
- **Phase 1**: Core RAG with knowledge base retrieval
- **Phase 2**: Corrective RAG with RAGAS evaluation and web search fallback
- **Phase 3**: Healthcare safety features (emergency detection, medication safety)

The system now provides:
- Higher accuracy through relevance evaluation (targets 90% clinical accuracy)
- Better coverage through intelligent web search fallback (15-20% of queries)
- Critical safety features for emergency situations (100% recall target)
- Medication interaction warnings for common diabetes drugs
- Proper medical citations and source attribution

**Technical Architecture:**
- Tool-based orchestration (LLM decides workflow via system prompt)
- RAGAS automated quality scoring (eliminates need for custom grading logic)
- Fail-safe design (errors default to "relevant" in healthcare context)
- Uses Claude 3.7 Sonnet for RAGAS evaluation, Claude Sonnet 4 for primary responses

**Next Steps:**
1. Deploy Bedrock Knowledge Base with diabetes content (WebMD scraper already exists)
2. Set environment variables: DIABETES_KB_ID, BEDROCK_EVAL_MODEL_ID, TAVILY_API_KEY
3. Test with clinical validation queries (see plan document Section 9.2)
4. Tune RAGAS threshold based on expert feedback (current: 0.5)
5. Run Phase 4 testing and validation (clinical accuracy ≥90%)

**Dependencies:**
- Requires AWS Bedrock access with Claude models
- Requires Tavily API key for web search
- Requires Knowledge Base deployment before full functionality

**Cost Impact:**
- Estimated $0.018 per query (76% reduction from original architecture)
- RAGAS evaluation adds ~$0.003 per query
- Web search adds ~$0.005 per triggered search (15-20% of queries)

---

**References:**
- Implementation Plan: `docs/2025-10-15-11-15-diabetes-corrective-rag-implementation-plan.md`
- RAGAS Documentation: https://docs.ragas.io
- Tavily API: https://docs.tavily.com

---

### Fixed - Deployment Documentation Error

**Issue Reported:**
```bash
$ npx cdk deploy DiabetesKBStack --profile medView
No stacks match the name(s) DiabetesKBStack
```

**Root Cause Analysis:**
- Documentation referenced non-existent `DiabetesKBStack` in CDK
- The implementation plan assumed automated KB deployment that doesn't exist
- Actual CDK stacks are: `StrandsChatWaf`, `MihcStack`, `StrandsChat`

**Files Updated:**
1. **IMPLEMENTATION_SUMMARY.md**
   - Added root cause analysis section at top
   - Corrected deployment steps (manual KB creation)
   - Updated troubleshooting with actual fix
   - Added quick start guide with corrected workflow
   - Fixed all references to DiabetesKBStack

**Corrected Deployment Path:**
1. Create Bedrock Knowledge Base manually via AWS Console
2. Configure environment variables directly in Lambda OR via parameter.ts
3. Deploy `StrandsChat` stack (not DiabetesKBStack)

**Future Work:**
- Consider writing `cdk/lib/diabetes-kb-stack.ts` to automate KB creation
- Add `diabetesKnowledgeBaseId` to `parameter.types.ts` schema
- Document automated KB deployment when implemented

**Impact:**
- ✅ Deployment instructions now accurate
- ✅ Users can proceed with manual KB creation
- ✅ Clear troubleshooting for this specific error
- 📋 Automated KB deployment remains future enhancement

