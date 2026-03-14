"""
GitHub Actions MCP Server - Agentic Workflows Operations Dashboard.

Exposes tools for monitoring and operating GitHub Actions workflows via the
Model Context Protocol (MCP), enabling AI agents and Copilot to interact with
your CI/CD pipelines.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from pydantic_settings import BaseSettings

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    github_token: str = Field(
        default="",
        description="GitHub Personal Access Token (PAT) with `repo` and `workflow` scopes.",
    )
    github_api_base: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL (override for GitHub Enterprise).",
    )
    default_owner: str = Field(
        default="",
        description="Default repository owner (org or user) used when owner is omitted.",
    )
    default_repo: str = Field(
        default="",
        description="Default repository name used when repo is omitted.",
    )

    model_config = {"env_prefix": "GITHUB_", "env_file": ".env", "extra": "ignore"}


settings = Settings()

# ---------------------------------------------------------------------------
# GitHub API client helpers
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = settings.github_token or os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _resolve(owner: str, repo: str) -> tuple[str, str]:
    """Return (owner, repo), falling back to configured defaults."""
    return (owner or settings.default_owner, repo or settings.default_repo)


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.github_api_base, headers=_headers(), timeout=30)


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    with _client() as client:
        resp = client.get(path, params={k: v for k, v in (params or {}).items() if v is not None})
        resp.raise_for_status()
        return resp.json()


def _post(path: str, json: dict[str, Any] | None = None) -> Any:
    with _client() as client:
        resp = client.post(path, json=json)
        resp.raise_for_status()
        # 204 No Content returns an empty body
        if resp.status_code == 204:
            return {"status": "ok"}
        return resp.json()


# ---------------------------------------------------------------------------
# MCP server definition
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "github-actions-dashboard",
    instructions=(
        "You are a GitHub Actions operations assistant. "
        "Use these tools to inspect and manage CI/CD workflows, runs, jobs, and artifacts "
        "for any GitHub repository."
    ),
)

# ---------------------------------------------------------------------------
# Tools – Workflows
# ---------------------------------------------------------------------------


@mcp.tool()
def list_workflows(
    owner: str = "",
    repo: str = "",
    per_page: int = 30,
    page: int = 1,
) -> dict[str, Any]:
    """List all workflows defined in a GitHub repository.

    Args:
        owner: Repository owner (org or user). Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        per_page: Number of results per page (max 100).
        page: Page number for pagination.

    Returns:
        A dict with ``total_count`` and ``workflows`` list, each entry containing
        id, name, path, state, created_at, updated_at, url, html_url, badge_url.
    """
    owner, repo = _resolve(owner, repo)
    return _get(f"/repos/{owner}/{repo}/actions/workflows", {"per_page": per_page, "page": page})


@mcp.tool()
def get_workflow(
    workflow_id: str,
    owner: str = "",
    repo: str = "",
) -> dict[str, Any]:
    """Get details of a specific workflow by its ID or file name.

    Args:
        workflow_id: Workflow ID (integer) or workflow file name (e.g. ``ci.yml``).
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Workflow object with id, name, state, path, and badge_url.
    """
    owner, repo = _resolve(owner, repo)
    return _get(f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}")


# ---------------------------------------------------------------------------
# Tools – Workflow Runs
# ---------------------------------------------------------------------------


@mcp.tool()
def list_workflow_runs(
    owner: str = "",
    repo: str = "",
    workflow_id: str = "",
    branch: str = "",
    event: str = "",
    status: str = "",
    actor: str = "",
    per_page: int = 30,
    page: int = 1,
) -> dict[str, Any]:
    """List workflow runs for a repository or a specific workflow.

    Args:
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        workflow_id: Optional workflow ID or file name to filter runs.
        branch: Filter runs by branch name.
        event: Filter by event type (e.g. ``push``, ``pull_request``, ``schedule``).
        status: Filter by status: ``queued``, ``in_progress``, ``completed``,
                ``waiting``, ``requested``, ``action_required``, ``failure``,
                ``success``, ``neutral``, ``cancelled``, ``skipped``,
                ``timed_out``.
        actor: Filter by the GitHub login of the user who triggered the run.
        per_page: Results per page (max 100).
        page: Page number.

    Returns:
        Dict with ``total_count`` and ``workflow_runs`` list.
    """
    owner, repo = _resolve(owner, repo)
    params: dict[str, Any] = {
        "branch": branch,
        "event": event,
        "status": status,
        "actor": actor,
        "per_page": per_page,
        "page": page,
    }
    if workflow_id:
        path = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
    else:
        path = f"/repos/{owner}/{repo}/actions/runs"
    return _get(path, params)


@mcp.tool()
def get_workflow_run(
    run_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, Any]:
    """Get detailed information about a specific workflow run.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Workflow run object including status, conclusion, timing, head_commit,
        triggering_actor, and referenced workflow.
    """
    owner, repo = _resolve(owner, repo)
    return _get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")


@mcp.tool()
def get_workflow_run_usage(
    run_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, Any]:
    """Get billable minute usage and timing for a workflow run.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Dict with ``billable`` timing per runner OS and ``run_duration_ms``.
    """
    owner, repo = _resolve(owner, repo)
    return _get(f"/repos/{owner}/{repo}/actions/runs/{run_id}/timing")


@mcp.tool()
def cancel_workflow_run(
    run_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, Any]:
    """Cancel a workflow run that is queued or in progress.

    Args:
        run_id: The unique identifier of the workflow run to cancel.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        ``{"status": "ok"}`` on success.
    """
    owner, repo = _resolve(owner, repo)
    return _post(f"/repos/{owner}/{repo}/actions/runs/{run_id}/cancel")


@mcp.tool()
def rerun_workflow_run(
    run_id: int,
    owner: str = "",
    repo: str = "",
    enable_debug_logging: bool = False,
) -> dict[str, Any]:
    """Re-run a complete workflow run (all jobs).

    Args:
        run_id: The unique identifier of the workflow run to re-run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        enable_debug_logging: Whether to enable debug-level logging for the re-run.

    Returns:
        ``{"status": "ok"}`` on success.
    """
    owner, repo = _resolve(owner, repo)
    return _post(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun",
        {"enable_debug_logging": enable_debug_logging},
    )


@mcp.tool()
def rerun_failed_jobs(
    run_id: int,
    owner: str = "",
    repo: str = "",
    enable_debug_logging: bool = False,
) -> dict[str, Any]:
    """Re-run only the failed jobs of a workflow run.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        enable_debug_logging: Whether to enable debug logging for the re-run.

    Returns:
        ``{"status": "ok"}`` on success.
    """
    owner, repo = _resolve(owner, repo)
    return _post(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs",
        {"enable_debug_logging": enable_debug_logging},
    )


@mcp.tool()
def trigger_workflow(
    workflow_id: str,
    ref: str,
    owner: str = "",
    repo: str = "",
    inputs: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Trigger a workflow_dispatch event to start a workflow run manually.

    Args:
        workflow_id: Workflow ID or file name (e.g. ``deploy.yml``).
        ref: The git ref (branch, tag, or SHA) on which to run the workflow.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        inputs: Optional key-value pairs matching the workflow's ``on.workflow_dispatch.inputs``.

    Returns:
        ``{"status": "ok"}`` on success (GitHub returns 204 No Content).
    """
    owner, repo = _resolve(owner, repo)
    payload: dict[str, Any] = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs
    return _post(f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches", payload)


# ---------------------------------------------------------------------------
# Tools – Jobs
# ---------------------------------------------------------------------------


@mcp.tool()
def list_workflow_jobs(
    run_id: int,
    owner: str = "",
    repo: str = "",
    filter: str = "latest",
    per_page: int = 30,
    page: int = 1,
) -> dict[str, Any]:
    """List jobs for a workflow run.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        filter: ``latest`` (default) returns only the most recent attempt per job;
                ``all`` returns all attempts.
        per_page: Results per page (max 100).
        page: Page number.

    Returns:
        Dict with ``total_count`` and ``jobs`` list, each with id, name, status,
        conclusion, started_at, completed_at, steps, runner_name, and html_url.
    """
    owner, repo = _resolve(owner, repo)
    return _get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs",
        {"filter": filter, "per_page": per_page, "page": page},
    )


@mcp.tool()
def get_job(
    job_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, Any]:
    """Get details for a specific job within a workflow run.

    Args:
        job_id: The unique identifier of the job.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Job object with id, run_id, name, status, conclusion, steps, runner_name,
        started_at, completed_at, and html_url.
    """
    owner, repo = _resolve(owner, repo)
    return _get(f"/repos/{owner}/{repo}/actions/jobs/{job_id}")


@mcp.tool()
def get_job_logs_url(
    job_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, str]:
    """Get the URL to download the log archive for a job.

    Args:
        job_id: The unique identifier of the job.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Dict with ``logs_url`` pointing to the downloadable log archive.
    """
    owner, repo = _resolve(owner, repo)
    with _client() as client:
        resp = client.get(
            f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs",
            follow_redirects=False,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            return {"logs_url": resp.headers.get("location", "")}
        resp.raise_for_status()
        return {"logs_url": str(resp.url)}


@mcp.tool()
def get_workflow_run_logs_url(
    run_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, str]:
    """Get the URL to download the combined log archive for an entire workflow run.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Dict with ``logs_url`` pointing to the downloadable zip archive.
    """
    owner, repo = _resolve(owner, repo)
    with _client() as client:
        resp = client.get(
            f"/repos/{owner}/{repo}/actions/runs/{run_id}/logs",
            follow_redirects=False,
        )
        if resp.status_code in (301, 302, 303, 307, 308):
            return {"logs_url": resp.headers.get("location", "")}
        resp.raise_for_status()
        return {"logs_url": str(resp.url)}


# ---------------------------------------------------------------------------
# Tools – Artifacts
# ---------------------------------------------------------------------------


@mcp.tool()
def list_run_artifacts(
    run_id: int,
    owner: str = "",
    repo: str = "",
    per_page: int = 30,
    page: int = 1,
) -> dict[str, Any]:
    """List artifacts produced by a workflow run.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        per_page: Results per page (max 100).
        page: Page number.

    Returns:
        Dict with ``total_count`` and ``artifacts`` list, each with id, name,
        size_in_bytes, created_at, expires_at, archive_download_url.
    """
    owner, repo = _resolve(owner, repo)
    return _get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts",
        {"per_page": per_page, "page": page},
    )


@mcp.tool()
def list_repo_artifacts(
    owner: str = "",
    repo: str = "",
    name: str = "",
    per_page: int = 30,
    page: int = 1,
) -> dict[str, Any]:
    """List all artifacts for a repository (across all runs).

    Args:
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        name: Optional filter by artifact name.
        per_page: Results per page (max 100).
        page: Page number.

    Returns:
        Dict with ``total_count`` and ``artifacts`` list.
    """
    owner, repo = _resolve(owner, repo)
    return _get(
        f"/repos/{owner}/{repo}/actions/artifacts",
        {"name": name, "per_page": per_page, "page": page},
    )


# ---------------------------------------------------------------------------
# Tools – Dashboard / summary helpers
# ---------------------------------------------------------------------------


@mcp.tool()
def get_run_summary(
    run_id: int,
    owner: str = "",
    repo: str = "",
) -> dict[str, Any]:
    """Return a concise operational summary for a workflow run.

    Combines run details, job statuses, and artifact counts into a single
    structured view — ideal for dashboards and quick status checks.

    Args:
        run_id: The unique identifier of the workflow run.
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.

    Returns:
        Dict with keys: ``run`` (core run info), ``jobs_summary`` (per-job
        status/conclusion list), ``artifacts_count``.
    """
    owner, repo = _resolve(owner, repo)

    run = _get(f"/repos/{owner}/{repo}/actions/runs/{run_id}")
    jobs_data = _get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", {"per_page": 100}
    )
    artifacts_data = _get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts", {"per_page": 1}
    )

    jobs_summary = [
        {
            "id": j["id"],
            "name": j["name"],
            "status": j["status"],
            "conclusion": j.get("conclusion"),
            "started_at": j.get("started_at"),
            "completed_at": j.get("completed_at"),
            "html_url": j.get("html_url"),
        }
        for j in jobs_data.get("jobs", [])
    ]

    return {
        "run": {
            "id": run["id"],
            "name": run.get("name"),
            "workflow_id": run.get("workflow_id"),
            "head_branch": run.get("head_branch"),
            "head_sha": run.get("head_sha"),
            "event": run.get("event"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "html_url": run.get("html_url"),
            "run_number": run.get("run_number"),
            "run_attempt": run.get("run_attempt"),
            "triggering_actor": run.get("triggering_actor", {}).get("login"),
        },
        "jobs_summary": jobs_summary,
        "artifacts_count": artifacts_data.get("total_count", 0),
    }


@mcp.tool()
def list_failed_runs(
    owner: str = "",
    repo: str = "",
    workflow_id: str = "",
    branch: str = "",
    per_page: int = 10,
) -> dict[str, Any]:
    """List the most recent failed workflow runs for quick triage.

    Args:
        owner: Repository owner. Uses GITHUB_DEFAULT_OWNER if omitted.
        repo: Repository name. Uses GITHUB_DEFAULT_REPO if omitted.
        workflow_id: Optional workflow ID or file name to scope the query.
        branch: Optional branch name to narrow results.
        per_page: Number of failed runs to return (max 100).

    Returns:
        Dict with ``total_count`` and ``workflow_runs`` list of failed runs.
    """
    owner, repo = _resolve(owner, repo)
    params: dict[str, Any] = {
        "status": "failure",
        "branch": branch,
        "per_page": per_page,
    }
    if workflow_id:
        path = f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs"
    else:
        path = f"/repos/{owner}/{repo}/actions/runs"
    return _get(path, params)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server using STDIO transport (default for MCP clients)."""
    mcp.run()


if __name__ == "__main__":
    main()
