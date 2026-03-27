# Troubleshooting Guide

Common issues and their solutions when working with AICA.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [LLM Connection Errors](#llm-connection-errors)
- [Neo4j Connection Errors](#neo4j-connection-errors)
- [Scanning and Indexing Issues](#scanning-and-indexing-issues)
- [Graph Building Errors](#graph-building-errors)
- [Performance Issues](#performance-issues)
- [Configuration Problems](#configuration-problems)

---

## Installation Issues

### Issue: `pip install` fails with dependency conflict

**Symptom:**

```
ERROR: Cannot install aica because these package versions have conflicts.
```

**Solution:**

1. Create a fresh virtual environment:

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Upgrade pip:

```bash
pip install --upgrade pip
```

3. Install AICA:

```bash
pip install -e ".[dev]"
```

---

### Issue: `aica: command not found`

**Symptom:**

```bash
aica version
# bash: aica: command not found
```

**Solutions:**

1. **Verify installation:**

```bash
pip list | grep aica
# Should show: aica  0.1.0
```

2. **Check PATH:**

```bash
which python
# Note the directory, e.g., /home/user/venv/bin/python
ls /home/user/venv/bin/aica  # Should exist
```

3. **Re-install with --force:**

```bash
pip install --force-reinstall -e ".[dev]"
```

4. **Try with python -m:**

```bash
python -m aica.interfaces.cli version
```

---

### Issue: Python 3.11+ not found

**Symptom:**

```
ERROR: Python 3.11 or higher is required.
```

**Solutions:**

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv
```

**macOS (Homebrew):**

```bash
brew install python@3.11
```

**Windows:**

Download from [python.org/downloads](https://www.python.org/downloads/)

---

## LLM Connection Errors

### Issue: Ollama connection refused

**Symptom:**

```
LLMConnectionError: Connection refused to http://localhost:11434
```

**Solutions:**

1. **Check if Ollama is running:**

```bash
curl http://localhost:11434/api/version
# Should return JSON with version info
```

2. **Start Ollama:**

**macOS/Linux:**

```bash
ollama serve
```

**Windows:**

```bash
ollama serve
```

3. **Verify Ollama is on correct port:**

```bash
ss -tlnp | grep 11434  # Linux
lsof -i :11434         # macOS
netstat -an | findstr 11434  # Windows
```

4. **Check AICA config:**

```bash
grep OLLAMA .env
# AICA_OLLAMA_BASE_URL=http://localhost:11434
```

---

### Issue: Ollama model not found

**Symptom:**

```
LLMError: Model 'codellama' not found
```

**Solutions:**

1. **List installed models:**

```bash
ollama list
```

2. **Pull the model:**

```bash
ollama pull codellama
# or
ollama pull qwen2.5-coder
```

3. **Verify model name in .env:**

```env
AICA_OLLAMA_MODEL=codellama  # Must match exactly
```

---

### Issue: OpenRouter authentication failed

**Symptom:**

```
LLMAuthError: Authentication failed (401)
```

**Solutions:**

1. **Verify API key format:**

```bash
echo $AICA_OPENROUTER_API_KEY
# Should start with: sk-or-v1-...
```

2. **Check key validity:**

```bash
curl -H "Authorization: Bearer $AICA_OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models
# Should return JSON with model list
```

3. **Regenerate key:**

Visit [openrouter.ai/keys](https://openrouter.ai/keys), delete old key, create new one.

4. **Check for quotes in .env:**

```env
# ❌ Wrong:
AICA_OPENROUTER_API_KEY="sk-or-v1-..."

# ✅ Correct:
AICA_OPENROUTER_API_KEY=sk-or-v1-...
```

---

### Issue: OpenRouter rate limit exceeded

**Symptom:**

```
LLMRateLimitError: Rate limit exceeded (429)
```

**Solutions:**

1. **Wait and retry** — AICA automatically retries with exponential backoff
2. **Check usage:** Visit [openrouter.ai/activity](https://openrouter.ai/activity)
3. **Add credits:** Add funds to your OpenRouter account
4. **Switch model:** Use a cheaper model:

```env
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini  # Cheaper than gpt-4o
```

---

### Issue: LLM timeout

**Symptom:**

```
LLMTimeoutError: Request timed out after 60 seconds
```

**Solutions:**

1. **Increase timeout in .env:**

```env
AICA_LLM_TIMEOUT=120  # 2 minutes
```

2. **Check network connectivity:**

```bash
ping openrouter.ai
# or
ping localhost  # for Ollama
```

3. **Use a faster model:**

```env
AICA_OPENROUTER_MODEL=anthropic/claude-3-haiku  # Faster than Sonnet
```

---

## Neo4j Connection Errors

### Issue: Neo4j connection refused

**Symptom:**

```
GraphConnectionError: Connection refused to bolt://localhost:7687
```

**Solutions:**

1. **Check if Neo4j is running:**

```bash
docker ps | grep neo4j
# or
curl http://localhost:7474  # Should return HTML
```

2. **Start Neo4j Docker:**

```bash
docker start aica-neo4j
# or
docker run --rm -d \
  --name aica-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:latest
```

3. **Check firewall:**

```bash
# Allow port 7687
sudo ufw allow 7687  # Linux
```

4. **Verify URI format:**

```env
# ✅ Correct:
AICA_NEO4J_URI=bolt://localhost:7687

# ❌ Wrong:
AICA_NEO4J_URI=http://localhost:7687
AICA_NEO4J_URI=localhost:7687
```

---

### Issue: Neo4j authentication failed

**Symptom:**

```
GraphAuthError: Authentication failed for user 'neo4j'
```

**Solutions:**

1. **Check Docker startup logs:**

```bash
docker logs aica-neo4j | grep AUTH
# Should show: Remote interface available at http://localhost:7474/
```

2. **Verify password:**

```bash
# Check what password was set when starting Neo4j
docker inspect aica-neo4j | grep NEO4J_AUTH
```

3. **Reset password via Browser:**

- Open [http://localhost:7474](http://localhost:7474)
- Log in with old password
- Run:
  ```cypher
  ALTER USER neo4j SET PASSWORD 'new_password'
  ```
- Update `.env` with new password

4. **For Neo4j Aura:**

- Go to [aura.neo4j.io](https://aura.neo4j.io)
- Click instance → **Reset Password**
- Update `.env`

---

### Issue: Neo4j Aura certificate error

**Symptom:**

```
GraphConnectionError: SSL certificate verification failed
```

**Solutions:**

1. **Use secure URI:**

```env
# ✅ Correct for Aura:
AICA_NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io

# ❌ Wrong:
AICA_NEO4J_URI=bolt://xxxxx.databases.neo4j.io
```

2. **Update neo4j Python driver:**

```bash
pip install --upgrade neo4j
```

---

## Scanning and Indexing Issues

### Issue: Permission denied when scanning

**Symptom:**

```
PermissionError: [Errno 13] Permission denied: '/path/to/repo'
```

**Solutions:**

1. **Check directory permissions:**

```bash
ls -la /path/to/repo
# Should be readable by current user
```

2. **Change ownership:**

```bash
sudo chown -R $USER:$USER /path/to/repo
```

3. **Run with correct user:**

```bash
# Don't use sudo for AICA commands
aica scan-repo --path /path/to/repo
```

---

### Issue: No .repo_intelligence directory found

**Symptom:**

```
Error: No .repo_intelligence/ directory found at /path/to/repo
```

**Solutions:**

1. **Run scan-repo first:**

```bash
cd /path/to/repo
aica scan-repo
```

2. **Verify output:**

```bash
ls -la .repo_intelligence/
# Should contain: structure.json, routes.json, components.json, etc.
```

3. **Check write permissions:**

```bash
touch .repo_intelligence/test.txt
# If this fails, fix directory permissions
```

---

### Issue: Tree-sitter parse errors

**Symptom:**

```
ERROR: Failed to parse src/MyComponent.tsx: tree-sitter error
```

**Solutions:**

1. **Check syntax errors:**

```bash
npx tsc --noEmit
# Fix any TypeScript syntax errors
```

2. **Update tree-sitter:**

```bash
pip install --upgrade tree-sitter tree-sitter-typescript
```

3. **Skip problematic files:**

AICA logs errors but continues. Check logs:

```bash
AICA_LOG_LEVEL=DEBUG aica index-code 2>&1 | grep -i error
```

---

### Issue: Slow scans on large repositories

**Symptom:**

```
aica scan-repo takes >5 minutes on a 1000-file repo
```

**Solutions:**

1. **Use SSD storage** — HDD I/O can bottleneck scanning

2. **Exclude build directories:**

AICA already excludes `node_modules`, `.next`, `dist`, `build`, `out`.

Verify these are ignored:

```bash
ls .repo_intelligence/ | wc -l
# Should not include build artifacts
```

3. **Run on a faster machine** or increase CPU resources (for containers)

4. **Disable verbose mode:**

```bash
aica scan-repo  # Without --verbose
```

---

## Graph Building Errors

### Issue: Constraint violation errors

**Symptom:**

```
GraphQueryError: Node already exists with label `File` and property `path`
```

**Solutions:**

1. **Clear the database:**

```cypher
MATCH (n) DETACH DELETE n
```

2. **Re-run build-graph:**

```bash
aica build-graph
```

3. **Or drop constraints:**

```cypher
SHOW CONSTRAINTS;  -- List all
DROP CONSTRAINT file_path_unique IF EXISTS;
DROP CONSTRAINT function_id_unique IF EXISTS;
-- ... repeat for all 7 constraints
```

Then re-run `aica build-graph` (will recreate constraints).

---

### Issue: Missing AST artifacts

**Symptom:**

```
WARNING: No imports.json found, skipping import edges
WARNING: No functions.json found, skipping function nodes
```

**Solutions:**

1. **Run index-code first:**

```bash
aica index-code
```

2. **Verify AST directory:**

```bash
ls .repo_intelligence/ast/
# Should contain: imports.json, functions.json, exports.json, call_graph.json,
# hooks.json, components.json, types.json
```

3. **Check for write errors:**

```bash
AICA_LOG_LEVEL=DEBUG aica index-code 2>&1 | grep -i error
```

---

### Issue: Empty graph after build

**Symptom:**

```
Graph Summary: 0 files, 0 functions, 0 components
```

**Solutions:**

1. **Check artifact files are non-empty:**

```bash
ls -lh .repo_intelligence/ast/
# Files should be >100 bytes (except for empty repos)
```

2. **Inspect functions.json:**

```bash
head .repo_intelligence/ast/functions.json
# Should contain array of function objects
```

3. **Run scan and index again:**

```bash
aica scan-repo
aica index-code
aica build-graph
```

---

## Performance Issues

### Issue: High memory usage during graph build

**Symptom:**

```
Memory usage reaches 4GB+ during aica build-graph
```

**Solutions:**

1. **Increase Neo4j heap size:**

For Docker:

```bash
docker run --rm -d \
  --name aica-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  -e NEO4J_dbms_memory_heap_max__size=2G \
  neo4j:latest
```

2. **Run on machine with more RAM** (minimum 8GB recommended for large repos)

3. **Process repo in chunks:**

Split large monorepos into smaller sub-projects and build graphs separately.

---

### Issue: Slow Cypher queries

**Symptom:**

```
Query takes >30 seconds to return results
```

**Solutions:**

1. **Add LIMIT clause:**

```cypher
MATCH (f:File)-[:IMPORTS]->(m:Module)
RETURN f, m
LIMIT 100  -- Don't fetch all results
```

2. **Use indexes:**

```cypher
// Create index on frequently-queried properties
CREATE INDEX file_path_idx FOR (f:File) ON (f.path);
CREATE INDEX function_name_idx FOR (fn:Function) ON (fn.name);
```

3. **Profile queries:**

```cypher
PROFILE MATCH (f:File)-[:IMPORTS]->(m:Module)
RETURN f, m
LIMIT 100
// Check "db hits" in execution plan
```

4. **Use more specific patterns:**

```cypher
// ❌ Slow:
MATCH (n) RETURN n

// ✅ Fast:
MATCH (f:File {path: "src/App.tsx"})-[:IMPORTS]->(m) RETURN m
```

---

## Configuration Problems

### Issue: Settings not loading from .env

**Symptom:**

```bash
aica status
# Shows defaults instead of .env values
```

**Solutions:**

1. **Verify .env location:**

```bash
pwd  # Should be in same directory as .env
ls -la .env
```

2. **Check .env syntax:**

```env
# ❌ Wrong (no spaces around =):
AICA_LOG_LEVEL = DEBUG

# ✅ Correct:
AICA_LOG_LEVEL=DEBUG
```

3. **No export keyword:**

```env
# ❌ Wrong:
export AICA_LOG_LEVEL=DEBUG

# ✅ Correct:
AICA_LOG_LEVEL=DEBUG
```

4. **Force reload:**

```bash
source .env  # If you want to export to shell
aica status  # AICA reads .env directly
```

---

### Issue: Secrets exposed in logs

**Symptom:**

```
Log output contains API keys or passwords
```

**Solutions:**

1. **Verify SecretStr usage:**

AICA automatically masks `AICA_OPENROUTER_API_KEY` and `AICA_NEO4J_PASSWORD`.

2. **Don't use DEBUG in production:**

```env
AICA_DEBUG=false
AICA_LOG_LEVEL=INFO  # Not DEBUG
```

3. **Check log files:**

```bash
grep -i "password\|api.key" logs/*.log
# Should show: ********** (masked)
```

---

## Getting Help

If you're still stuck:

1. **Check logs:**

```bash
AICA_LOG_LEVEL=DEBUG aica [command] 2>&1 | tee debug.log
```

2. **Create GitHub issue:**

Include:

- AICA version (`aica version`)
- Python version (`python --version`)
- OS and architecture
- Full error message
- Steps to reproduce

3. **Community:**

- **GitHub Discussions:** Ask questions
- **GitHub Issues:** Report bugs

---

## Additional Resources

- **[CLI Reference](cli.md)** — All commands and options
- **[Configuration Reference](configuration.md)** — All environment variables
- **[Neo4j Graph Guide](neo4j-graph.md)** — Graph schema and queries
- **[Tutorials](tutorials.md)** — Step-by-step guides
- **[API Reference](api-reference.md)** — Programmatic usage
