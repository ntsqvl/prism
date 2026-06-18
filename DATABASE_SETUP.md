# Database & Deployment Setup Guide

## ⚠️ IMMEDIATE ACTION REQUIRED

Your new infrastructure requires PostgreSQL. Without it, you'll get database connection errors when trying to use GiGi's document ingestion pipeline.

---

## Option 1: Local Development (Fastest - 10 minutes)

### Step 1: Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo service postgresql start
```

**Windows:**
- Download from https://www.postgresql.org/download/windows/
- Run installer, note the password you set for `postgres` user

### Step 2: Create Local Database

```bash
# Connect to PostgreSQL
psql -U postgres

# In the psql prompt:
CREATE DATABASE band_lab;
\q
```

### Step 3: Set DATABASE_URL in .env

```bash
# .env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/band_lab
```

### Step 4: Initialize Tables

```bash
# Option A: Run the SQL script directly
psql -U postgres -d band_lab -f band_lab_dbs_script.sql

# Option B: Let the app create tables on startup
python database.py
# Should output: ✅ Database connection successful!
```

### Step 5: Test Connection

```bash
python database.py
```

Expected output:
```
✅ Database connection successful!
   PostgreSQL version: 14.x.x
```

---

## Option 2: Cloud Database (Production-Ready - 15 minutes)

### Digital Ocean (Pre-configured in code)

1. **Create managed database:**
   - Go to DigitalOcean → Databases → Create
   - Select PostgreSQL 14+
   - Note connection details

2. **Set DATABASE_URL:**
```bash
# .env
DATABASE_URL=postgresql://doadmin:YOUR_PASSWORD@db-postgresql-xxx.db.ondigitalocean.com:25060/defaultdb?sslmode=require
```

3. **Run migration script:**
```bash
# Option A: psql with remote connection
psql DATABASE_URL -f band_lab_dbs_script.sql

# Option B: App auto-initializes on first request
```

### AWS RDS

1. **Create RDS instance:** PostgreSQL 14+
2. **Security group:** Allow inbound port 5432 from your IP
3. **Set DATABASE_URL:**
```bash
DATABASE_URL=postgresql://admin:PASSWORD@your-db.xxxxx.us-east-1.rds.amazonaws.com:5432/band_lab
```

### Heroku

```bash
# Create Postgres addon
heroku addons:create heroku-postgresql:standard-0

# Automatically sets DATABASE_URL
# Migrate:
heroku run "python database.py"
```

---

## Configuration Reference

### core/config.py

Your config file expects these environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# API Keys (for embedding service)
OPENAI_API_KEY=sk-...
# OR
AIML_API_KEY=...
AIML_BASE_URL=https://api.aiml.ai/v1

# Upload storage
UPLOAD_DIR=./uploads  # Local disk storage

# Embedding config
AIML_EMBEDDING_MODEL=text-embedding-3-small
MAX_EMBEDDING_RETRIES=3
```

### .env Template

```bash
# Database (required for production features)
DATABASE_URL=postgresql://localhost:5432/band_lab

# Mock mode (set to false when real agents ready)
MOCK_MODE=true

# Band integration (when ready)
BAND_ORG=your-org
BAND_API_KEY=your-api-key

# Embeddings (for document vectors)
OPENAI_API_KEY=sk-...

# Upload directory (relative to project root)
UPLOAD_DIR=./uploads
```

---

## Verification Checklist

After setup, verify everything works:

```bash
# 1. Test database connection
python database.py
# Expected: ✅ Database connection successful!

# 2. Check tables created
psql -d band_lab -c "\dt"
# Should list: vendor, vendor_document, document_chunk, embedding_job, etc.

# 3. Start the app
uv run uvicorn main:app --reload

# 4. Test endpoints
curl http://localhost:8000/health
# Should show: "database": "connected"

# 5. Test document upload workflow
# - Use Postman or API docs at /docs
# - POST /vendor/{vendor_id}/upload (create vendor first!)
# - POST /cycle/{cycle_id}/ingest (trigger document processing)
```

---

## Timeline: When Do You Need This?

### IMMEDIATE (Today/Tomorrow)
- ❌ **Not needed** if using MOCK_MODE=true only
- ✅ **Needed** to test document upload → embedding pipeline
- ✅ **Needed** before sharing with team for full testing

### Before Demo (3 days)
- ✅ Database must be set up and tested
- ✅ Document ingestion pipeline must work end-to-end
- ✅ Vector embeddings must be stored and retrievable

### Deployment (Before Final Judging)
- ✅ Use cloud database (DigitalOcean/AWS/Heroku)
- ✅ Not local development database!

---

## Troubleshooting

### Error: "DATABASE_URL is not set"
```
✗ Check your .env file
✗ Ensure DATABASE_URL= line exists
✗ Restart the app after adding it
```

### Error: "connection refused" (psycopg2)
```
✗ PostgreSQL not running: brew services start postgresql
✗ Wrong host: Use localhost for local, not 127.0.0.1
✗ Wrong port: Default is 5432
✗ Database doesn't exist: createdb band_lab
```

### Error: "permission denied" (psycopg2)
```
✗ Wrong password in DATABASE_URL
✗ User doesn't have create table permission
✗ Try: psql -U postgres -d band_lab -f band_lab_dbs_script.sql
```

### Error: "pgvector not installed"
```
# PostgreSQL extension missing
psql -d band_lab -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### MOCK_MODE but database errors?
```
# Only needed if:
# - You call vendor router endpoints directly
# - GiGi's services are imported and used
# - You run the embedding pipeline

# For pure mock workflow testing:
MOCK_MODE=true
# Database is optional but recommended for audit logging
```

---

## Quick Start: Recommended Flow

```bash
# 1. Install PostgreSQL (if not done)
brew install postgresql && brew services start postgresql

# 2. Create database
createdb band_lab

# 3. Add to .env
echo "DATABASE_URL=postgresql://localhost:5432/band_lab" >> .env

# 4. Run migrations
python database.py

# 5. Verify
curl http://localhost:8000/health

# 6. Start app
uv run uvicorn main:app --reload

# 7. Try it out!
# Go to http://localhost:8000/docs
```

---

## For Your Teammates

### Role 1 (GiGi) - Vector Database
- ✅ Already has all needed services
- ✅ Database URL should be set
- ✅ Verify embeddings are stored: `SELECT count(*) FROM document_chunk WHERE embedding IS NOT NULL;`

### Role 3, 4 (Agents)
- Database not needed for agents yet
- Can work with mock workflows using MOCK_MODE=true
- Will connect later once agent evaluation endpoints are DB-backed

### Role 5 (Frontend)
- Database not needed on frontend
- Just call API endpoints (they handle DB internally)
- `/docs` endpoint shows all available endpoints

---

## Next: Integration Testing

Once database is set up, test the full flow:

```bash
# 1. Create a procurement cycle
curl -X POST http://localhost:8000/cycle \
  -H "Content-Type: application/json" \
  -d '{"cycle_name": "Q3 Evaluation"}'
# Returns: { "cycle_id": "xxx-xxx-xxx" }

# 2. Add a vendor
curl -X POST http://localhost:8000/cycle/xxx-xxx-xxx/vendor/add \
  -H "Content-Type: application/json" \
  -d '{"vendor_name": "CloudSecure Inc"}'
# Returns: { "vendor_id": "yyy-yyy-yyy" }

# 3. Upload a document
curl -X POST http://localhost:8000/vendor/yyy-yyy-yyy/upload \
  -F "file=@contract.pdf"

# 4. Trigger ingestion
curl -X POST http://localhost:8000/cycle/xxx-xxx-xxx/ingest

# 5. Check documents were extracted
curl http://localhost:8000/vendor/yyy-yyy-yyy/documents

# 6. Check document completeness
curl http://localhost:8000/vendor/yyy-yyy-yyy/completeness
```

---

## Database Not Required For

- ✅ Mock workflow endpoints (`/api/start-evaluation`, `/api/submit-evaluation`, etc.)
- ✅ Conflict detection logic
- ✅ Agent evaluation orchestration
- ✅ Final recommendation logic

**Can use MOCK_MODE=true** for all of the above.

---

## Database Required For

- ❌ Document upload and storage
- ❌ PDF extraction and chunking
- ❌ Vector embeddings
- ❌ Document completeness scoring
- ❌ Context discovery classification
- ❌ Audit trail persistence

**Must set DATABASE_URL** for these.

---

## Decision: When to Set Up Database

### Now (Recommended)
- Want to test full ingestion pipeline
- GiGi's embedding service ready
- Team needs to test document upload

### Later (OK for another 1-2 days)
- Using mock workflow only
- Haven't received actual vendor documents yet
- Still building out agent evaluation logic

### Must Do Before Demo
- Required for judging! No exceptions
- Production database (not local)
- All pipeline stages tested

