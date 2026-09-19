# Setup

This repo runs `n8n` with:

- PostgreSQL for persistence
- external `task-runners`
- Python installed inside the Docker images
- a shared execution workspace at `workspace/`

The Docker setup is local-machine friendly: workflow scripts live in this repo under
`workspace/`, and both n8n containers see that folder at `/workspace`.

## What This Setup Does

- Mounts local `workspace/` into both `n8n` and `task-runners`
- Uses container Python at `/usr/local/bin/python`
- Shares `workspace/` between containers for scripts and generated files
- Exposes `public/` to n8n at `/home/node/files`
- Removes the previous n8n file allowlist restriction

Important: this does not remove Docker isolation itself. n8n can access what the containers can access. It does not automatically get unrestricted access to your full host outside mounted paths and container permissions.

## Prerequisites

- Docker with Compose support
- Python 3 on the host is optional, and only needed if you want to run scripts outside Docker

## Repo Layout

- `workspace/`: scripts, data, and generated outputs for workflows
- `public/`: files exposed inside the n8n container at `/home/node/files`
- `docker-compose.yml`: stack definition
- `Dockerfile.n8n`: main n8n image customization
- `Dockerfile.runners`: task runner customization

## First-Time Setup

1. Add any Python packages your workflows need to `workspace/requirements.txt`.

2. Start the stack:

```bash
docker compose up -d --build
```

3. Open n8n:

```text
http://localhost:5678
```

## Daily Workflow

When you need a new Python package:

1. Add it to `workspace/requirements.txt`.
2. Rebuild the stack:

```powershell
docker compose up -d --build
```

## How Python Is Wired

The active Python path configured for n8n is:

```text
/usr/local/bin/python
```

That path exists inside:

- `n8n-main`
- `n8n-runners`

`workspace/` is bind-mounted into both containers at `/workspace`, so scripts in this repo
are available locally and inside Docker without hardcoded host paths.

## Running Python From n8n

You can use Python in two common ways.

### Native Python / runner-backed execution

This setup enables n8n Python support with:

- `N8N_RUNNERS_ENABLED=true`
- `N8N_RUNNERS_MODE=external`
- `N8N_NATIVE_PYTHON_RUNNER=true`
- `N8N_PYTHON_ENABLED=true`
- `PYTHON_EXECUTABLE=/usr/local/bin/python`

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

[`workspace/scripts/test_python.py`](./workspace/scripts/test_python.py)

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

Check that the package is listed in `workspace/requirements.txt`, then rebuild:

```powershell
docker compose up -d --build
```

Then verify the containers can import it:

```powershell
docker exec n8n-main python -c "import package_name"
docker exec n8n-runners python -c "import package_name"
```

### n8n starts but Python execution fails

Verify Python is available in both containers:

```powershell
docker exec n8n-main python --version
docker exec n8n-runners python --version
```

Rebuild and restart the stack:

```bash
docker compose up -d --build
```

## Security Note

The previous `N8N_RESTRICT_FILE_ACCESS_TO` setting was removed. That gives workflows broader access inside the container environment, but not unlimited host access.

Current boundaries still include:

- Docker container isolation
- mounted paths only
- Linux file permissions
- whatever Docker Desktop or the Docker daemon is allowed to access

If you want true host-level unrestricted execution, that is a different security model and should be approached deliberately.
