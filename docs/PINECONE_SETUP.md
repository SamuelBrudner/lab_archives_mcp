# Pinecone Setup Guide

## Quick Start (5 minutes)

### **Step 1: Get API Keys**

You need two API keys:

1. **Pinecone API Key**
   - Visit: https://app.pinecone.io/
   - Sign up (free tier available)
   - Go to "API Keys" tab
   - Copy your API key

2. **OpenAI API Key** (if not already set)
   - Visit: https://platform.openai.com/api-keys
   - Create new key
   - Copy the key

### **Step 2: Populate `conf/secrets.yml`**

```bash
cp conf/secrets.example.yml conf/secrets.yml
$EDITOR conf/secrets.yml
```

Add your Pinecone and OpenAI keys in that file:

```yaml
OPENAI_API_KEY: "sk-..."
PINECONE_API_KEY: "your-pinecone-api-key"
PINECONE_ENVIRONMENT: "us-east-1"
```

All scripts and MCP tooling read from `conf/secrets.yml` by default (or the path set via `LABARCHIVES_CONFIG_PATH`). You can still override individual keys for a session by exporting environment variables if needed.

### **Step 3: Run Setup Script**

```bash
conda activate labarchives-mcp-pol
python scripts/setup_pinecone.py
```

Expected output:
```
🔧 Setting up Pinecone...

📝 Creating index 'labarchives-test'...
  • Dimension: 1536
  • Metric: cosine
  • Spec: Serverless (us-east-1)
✅ Index 'labarchives-test' created successfully!

🎉 Pinecone setup complete!
```

---

## Verify Setup

### **Test 1: Check Environment**

```bash
python -c "import os; print('PINECONE_API_KEY:', 'SET' if os.getenv('PINECONE_API_KEY') else 'NOT SET'); print('OPENAI_API_KEY:', 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET')"
```

Expected:
```
PINECONE_API_KEY: SET
OPENAI_API_KEY: SET
```

### **Test 2: Run Integration Tests**

```bash
pytest tests/test_vector_backend/integration/ -v -m integration
```

Expected:
```
test_pinecone_smoke.py::TestPineconeConnection::test_health_check PASSED
test_pinecone_smoke.py::TestPineconeConnection::test_stats_retrieval PASSED
test_pinecone_smoke.py::TestPineconeUpsert::test_upsert_single_chunk PASSED
test_pinecone_smoke.py::TestPineconeUpsert::test_upsert_empty_raises PASSED
test_pinecone_smoke.py::TestPineconeSearch::test_search_returns_results PASSED
test_pinecone_smoke.py::TestPineconeDelete::test_delete_by_id PASSED

============================== 6 passed in X.XXs ==============================
```

### **Test 3: Run End-to-End Workflow**

```bash
python scripts/test_e2e_workflow.py
```

Expected:
```
=== Vector Backend End-to-End Test ===

1. Loading configuration...
   ✓ Model: openai/text-embedding-3-small
   ✓ Chunk size: 400 tokens

2. Chunking text...
   ✓ Created 1 chunks

3. Generating embeddings...
   ✓ Generated 1 embeddings (1536 dimensions)

[... more steps ...]

=== End-to-End Test Complete! ===
```

---

## Troubleshooting

### **Error: "PINECONE_API_KEY not set"**

**Solution:** Export the environment variable:
```bash
export PINECONE_API_KEY="your-key-here"
```

Verify:
```bash
echo $PINECONE_API_KEY
```

### **Error: "pinecone not installed"**

**Solution:** Install the package:
```bash
pip install 'pinecone>=4.1'
```

Or reinstall the vector extras:
```bash
pip install -e ".[vector]"
```

### **Error: "Index already exists"**

**Solution:** This is fine! The setup script will detect it. If you want to start fresh:

```python
from pinecone import Pinecone
pc = Pinecone(api_key="your-key")
pc.delete_index("labarchives-test")
```

Then rerun `scripts/setup_pinecone.py`.

### **Error: "You have reached your index limit"**

**Solution:** Pinecone free tier allows 1 index. Options:
1. Delete an existing index in the Pinecone console
2. Upgrade to a paid plan
3. Use a different Pinecone account

### **Error: "Authentication failed"**

**Solution:** Check your API key:
1. Visit https://app.pinecone.io/
2. Go to "API Keys"
3. Copy the key exactly (no extra spaces)
4. Re-export: `export PINECONE_API_KEY="..."`

---

## Manual Setup (Alternative)

If the script doesn't work, you can create the index manually:

1. Visit https://app.pinecone.io/
2. Click "Create Index"
3. Settings:
   - **Name:** `labarchives-test`
   - **Dimensions:** `1536`
   - **Metric:** `cosine`
   - **Cloud:** AWS
   - **Region:** `us-east-1` (or your preferred region)
4. Click "Create Index"

Then update the environment variable:
```bash
export PINECONE_ENVIRONMENT="us-east-1"  # or your region
```

---

## Costs

**Pinecone Free Tier:**
- 1 serverless index
- ~100K vectors
- 1-2M queries/month
- Perfect for testing!

**OpenAI Costs:**
- Embeddings: $0.02 per 1M tokens
- For 10K chunks: ~$0.08 (one-time)
- Very affordable for testing

**Total estimated cost for Phase 1 testing: ~$0**
(Free tiers cover everything)

---

## Next Steps

Once setup is complete:

1. ✅ Run integration tests
2. ✅ Run E2E workflow
3. 🚀 Index real LabArchives data
4. 🔍 Test semantic search quality
5. 📊 Benchmark performance

See `PHASE1_COMPLETE.md` for full usage guide.
