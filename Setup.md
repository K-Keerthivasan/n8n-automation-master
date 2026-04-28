# Setup

This repo runs `n8n` with:

- PostgreSQL for persistence
- external `task-runners`
- a shared repo-local Python virtual environment at `.venv`
- a shared execution workspace at `workspace/`

The current Docker setup lets n8n use Python from the local repo venv instead of a separate container-only venv.

## What This Setup Does

- Mounts this repo into both `n8n` and `task-runners` at the same absolute path
- Uses `.venv/bin/python` as the Python executable for n8n
- Shares `workspace/` between containers for scripts and generated files
- Exposes `public/` to n8n at `/home/node/files`
- Removes the previous n8n file allowlist restriction

Important: this does not remove Docker isolation itself. n8n can access what the containers can access. It does not automatically get unrestricted access to your full host outside mounted paths and container permissions.

## Prerequisites

- Docker with Compose support
- Python 3 installed on the host

## Repo Layout

- `.venv/`: local Python virtual environment used by n8n
- `workspace/`: scripts, data, and generated outputs for workflows
- `public/`: files exposed inside the n8n container at `/home/node/files`
- `docker-compose.yml`: stack definition
- `Dockerfile.n8n`: main n8n image customization
- `Dockerfile.runners`: task runner customization

## First-Time Setup

1. Create the local virtual environment:

```bash
python3 -m venv .venv
```

2. Upgrade packaging tools inside the venv:

```bash
./.venv/bin/pip install --upgrade pip setuptools wheel
```

3. Install any Python packages your workflows need:

```bash
./.venv/bin/pip install requests pandas openpyxl
```

4. Optionally record packages in `workspace/requirements.txt` for your own reference.

5. Start the stack:

```bash
docker compose up -d --build
```

6. Open n8n:

```text
http://localhost:5678
```

## Daily Workflow

When you need a new Python package:

```bash
./.venv/bin/pip install <package-name>
```

The running containers use the same `.venv`, so package installs on the host are available to n8n without creating a second Python environment.

If you change only Python packages, you usually do not need to rebuild the images.

If you change Dockerfiles or Compose config, rebuild:

```bash
docker compose up -d --build
```

## How Python Is Wired

The active Python path configured for n8n is:

```text
/home/keerthi/Dev/ai/n8n-automation-master/.venv/bin/python
```

That path is mounted into:

- `n8n-main`
- `n8n-runners`

This is why the repo must be mounted into both containers at the same absolute location.

## Running Python From n8n

You can use Python in two common ways.

### Native Python / runner-backed execution

This setup enables n8n Python support with:

- `N8N_RUNNERS_ENABLED=true`
- `N8N_RUNNERS_MODE=external`
- `N8N_NATIVE_PYTHON_RUNNER=true`
- `N8N_PYTHON_ENABLED=true`
- `PYTHON_EXECUTABLE=.../.venv/bin/python`

### Execute Command node

Example commands:

```bash
python /workspace/scripts/test_python.py
```

```bash
python /workspace/scripts/my_script.py
```

```bash
pip list
```

## Test Script

A small verification script is included at:

[`workspace/scripts/test_python.py`](/home/keerthi/Dev/ai/n8n-automation-master/workspace/scripts/test_python.py)

Run it from n8n with:

```bash
python /workspace/scripts/test_python.py
```

Expected output should show:

- the Python executable path
- the Python version
- the current working directory

## Useful Docker Commands

Start or rebuild:

```bash
docker compose up -d --build
```

Stop:

```bash
docker compose down
```

View running services:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs -f n8n
```

```bash
docker compose logs -f task-runners
```

## Troubleshooting

### Python package installed but n8n cannot import it

Check that the package was installed into the repo-local venv:

```bash
./.venv/bin/pip show <package-name>
```

Then verify the containers still point at the same venv path:

```bash
docker exec n8n-main python -c "import sys; print(sys.prefix)"
docker exec n8n-runners python -c "import sys; print(sys.prefix)"
```

Both should print:

```text
/home/keerthi/Dev/ai/n8n-automation-master/.venv
```

### n8n starts but Python execution fails

Rebuild and restart the stack:

```bash
docker compose up -d --build
```

### Host package installs fail

If host `pip` cannot reach the package index, that is a host/network issue, not an n8n configuration issue.

## Security Note

The previous `N8N_RESTRICT_FILE_ACCESS_TO` setting was removed. That gives workflows broader access inside the container environment, but not unlimited host access.

Current boundaries still include:

- Docker container isolation
- mounted paths only
- Linux file permissions
- whatever Docker Desktop or the Docker daemon is allowed to access

If you want true host-level unrestricted execution, that is a different security model and should be approached deliberately.
