# GitHub Actions MCP Dashboard

An **MCP (Model Context Protocol) server** that turns your GitHub Actions
workflows into an AI-accessible operations dashboard. Connect it to GitHub
Copilot, Claude, or any other MCP-compatible AI client to monitor, triage,
and operate your CI/CD pipelines through natural-language conversations.

---

## Features

| Category | Tools |
|---|---|
| **Workflows** | `list_workflows`, `get_workflow` |
| **Runs** | `list_workflow_runs`, `get_workflow_run`, `get_workflow_run_usage`, `get_workflow_run_logs_url` |
| **Run control** | `cancel_workflow_run`, `rerun_workflow_run`, `rerun_failed_jobs`, `trigger_workflow` |
| **Jobs** | `list_workflow_jobs`, `get_job`, `get_job_logs_url` |
| **Artifacts** | `list_run_artifacts`, `list_repo_artifacts` |
| **Dashboard** | `get_run_summary` *(run + jobs + artifact count in one call)*, `list_failed_runs` |

---

## Requirements

- Python **3.10+**
- A GitHub **Personal Access Token (PAT)** with the `repo` and `workflow` scopes
  (or a fine-grained PAT with **Actions: Read/Write** and **Contents: Read**).

---

## Quick Start

### 1 — Clone & install

```bash
git clone https://github.com/AICraftworks-Demo/AgentCraftworks-NewRepoDemo.git
cd AgentCraftworks-NewRepoDemo
pip install -e .
```

### 2 — Configure

```bash
cp .env.example .env
# Edit .env and set GITHUB_TOKEN (and optionally DEFAULT_OWNER / DEFAULT_REPO)
```

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | **Yes** | PAT with `repo` + `workflow` scopes |
| `GITHUB_DEFAULT_OWNER` | No | Org/user used when `owner` is omitted from tool calls |
| `GITHUB_DEFAULT_REPO` | No | Repo name used when `repo` is omitted from tool calls |
| `GITHUB_API_BASE` | No | Override for GitHub Enterprise Server (e.g. `https://github.example.com/api/v3`) |

### 3 — Run the server

```bash
github-actions-mcp
# or
python -m github_actions_mcp.server
```

The server starts in **STDIO transport** mode, which is the default expected by
all MCP clients (VS Code Copilot, Claude Desktop, etc.).

---

## Connecting to an MCP Client

### GitHub Copilot in VS Code

Add the following to your VS Code `settings.json`
(or `.vscode/mcp.json` in the repo):

```json
{
  "mcp": {
    "servers": {
      "github-actions-dashboard": {
        "type": "stdio",
        "command": "github-actions-mcp",
        "env": {
          "GITHUB_TOKEN": "${env:GITHUB_TOKEN}",
          "GITHUB_DEFAULT_OWNER": "your-org",
          "GITHUB_DEFAULT_REPO": "your-repo"
        }
      }
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "github-actions-dashboard": {
      "command": "github-actions-mcp",
      "env": {
        "GITHUB_TOKEN": "ghp_your_token"
      }
    }
  }
}
```

---

## Example Conversations

Once connected, you can ask your AI assistant things like:

> "Show me the last 5 failed CI runs on the `main` branch."

> "Re-run only the failed jobs from run #1234."

> "Trigger the `deploy.yml` workflow on tag `v2.1.0` with `environment=production`."

> "Give me a summary of run #9876 — what jobs failed and are there any artifacts?"

> "Cancel all in-progress runs for the nightly workflow."

---

## Tool Reference

### `list_workflows(owner, repo, per_page, page)`
Lists all workflow definitions in a repository.

### `get_workflow(workflow_id, owner, repo)`
Gets details of one workflow by ID or file name (e.g. `ci.yml`).

### `list_workflow_runs(owner, repo, workflow_id, branch, event, status, actor, per_page, page)`
Lists runs with optional filters. `status` accepts: `queued`, `in_progress`,
`completed`, `waiting`, `failure`, `success`, `cancelled`, `timed_out`, etc.

### `get_workflow_run(run_id, owner, repo)`
Gets full details of a single run, including timing and commit info.

### `get_workflow_run_usage(run_id, owner, repo)`
Returns billable minutes and `run_duration_ms`.

### `cancel_workflow_run(run_id, owner, repo)`
Cancels a queued or in-progress run.

### `rerun_workflow_run(run_id, owner, repo, enable_debug_logging)`
Re-runs all jobs in a completed run.

### `rerun_failed_jobs(run_id, owner, repo, enable_debug_logging)`
Re-runs only the jobs that failed in the last attempt.

### `trigger_workflow(workflow_id, ref, owner, repo, inputs)`
Dispatches a `workflow_dispatch` event to start a run manually.

### `list_workflow_jobs(run_id, owner, repo, filter, per_page, page)`
Lists jobs for a run. `filter` is `latest` (default) or `all`.

### `get_job(job_id, owner, repo)`
Gets details for a single job including its steps.

### `get_job_logs_url(job_id, owner, repo)`
Returns the pre-signed URL to download a job's log archive.

### `get_workflow_run_logs_url(run_id, owner, repo)`
Returns the pre-signed URL to download the full run log zip.

### `list_run_artifacts(run_id, owner, repo, per_page, page)`
Lists artifacts produced by a specific run.

### `list_repo_artifacts(owner, repo, name, per_page, page)`
Lists all artifacts in a repository, optionally filtered by name.

### `get_run_summary(run_id, owner, repo)`
**Dashboard helper.** Returns run metadata, per-job status list, and artifact
count in a single call — ideal for at-a-glance status checks.

### `list_failed_runs(owner, repo, workflow_id, branch, per_page)`
Returns the most recent failed runs, optionally scoped to a workflow/branch.

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/
```

---

## License

MIT
