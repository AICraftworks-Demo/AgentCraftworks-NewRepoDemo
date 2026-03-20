"""
Unit tests for the GitHub Actions MCP server.

Uses unittest.mock.patch to intercept outbound calls so no real GitHub token
is required to run the test suite.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OWNER = "test-owner"
REPO = "test-repo"
BASE = "https://api.github.com"


def _fake_response(payload: Any, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response with the given JSON payload."""
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": "application/json"},
        content=json.dumps(payload).encode(),
        request=httpx.Request("GET", "https://api.github.com/test"),
    )


def _fake_redirect(location: str, status_code: int = 302) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        headers={"location": location, "Content-Type": "application/json"},
        content=b"",
        request=httpx.Request("GET", "https://api.github.com/test"),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_get(payload: Any, status_code: int = 200):
    """Context manager that patches github_actions_mcp.server._get."""
    return patch(
        "github_actions_mcp.server._get",
        return_value=payload,
    )


def _patch_post(payload: Any):
    return patch(
        "github_actions_mcp.server._post",
        return_value=payload,
    )


# ---------------------------------------------------------------------------
# Tests – list_workflows
# ---------------------------------------------------------------------------


def test_list_workflows_default_pagination():
    from github_actions_mcp.server import list_workflows

    expected = {"total_count": 2, "workflows": [{"id": 1, "name": "CI"}, {"id": 2, "name": "CD"}]}
    with _patch_get(expected) as mock_get:
        result = list_workflows(owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/workflows",
        {"per_page": 30, "page": 1},
    )
    assert result == expected


def test_list_workflows_custom_pagination():
    from github_actions_mcp.server import list_workflows

    expected = {"total_count": 5, "workflows": []}
    with _patch_get(expected) as mock_get:
        result = list_workflows(owner=OWNER, repo=REPO, per_page=10, page=2)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/workflows",
        {"per_page": 10, "page": 2},
    )
    assert result == expected


# ---------------------------------------------------------------------------
# Tests – get_workflow
# ---------------------------------------------------------------------------


def test_get_workflow_by_id():
    from github_actions_mcp.server import get_workflow

    expected = {"id": 42, "name": "CI", "state": "active"}
    with _patch_get(expected) as mock_get:
        result = get_workflow(workflow_id="42", owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(f"/repos/{OWNER}/{REPO}/actions/workflows/42")
    assert result["name"] == "CI"


def test_get_workflow_by_filename():
    from github_actions_mcp.server import get_workflow

    expected = {"id": 7, "name": "Deploy", "path": ".github/workflows/deploy.yml"}
    with _patch_get(expected) as mock_get:
        result = get_workflow(workflow_id="deploy.yml", owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/workflows/deploy.yml"
    )
    assert result["path"] == ".github/workflows/deploy.yml"


# ---------------------------------------------------------------------------
# Tests – list_workflow_runs
# ---------------------------------------------------------------------------


def test_list_workflow_runs_all_runs():
    from github_actions_mcp.server import list_workflow_runs

    expected = {"total_count": 10, "workflow_runs": []}
    with _patch_get(expected) as mock_get:
        result = list_workflow_runs(owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/runs",
        {"branch": "", "event": "", "status": "", "actor": "", "per_page": 30, "page": 1},
    )
    assert result["total_count"] == 10


def test_list_workflow_runs_scoped_to_workflow():
    from github_actions_mcp.server import list_workflow_runs

    expected = {"total_count": 3, "workflow_runs": []}
    with _patch_get(expected) as mock_get:
        list_workflow_runs(owner=OWNER, repo=REPO, workflow_id="ci.yml", status="failure")

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/workflows/ci.yml/runs",
        {"branch": "", "event": "", "status": "failure", "actor": "", "per_page": 30, "page": 1},
    )


def test_list_workflow_runs_with_branch_filter():
    from github_actions_mcp.server import list_workflow_runs

    with _patch_get({"total_count": 1, "workflow_runs": []}) as mock_get:
        list_workflow_runs(owner=OWNER, repo=REPO, branch="main", event="push")

    args = mock_get.call_args
    assert args[0][1]["branch"] == "main"
    assert args[0][1]["event"] == "push"


# ---------------------------------------------------------------------------
# Tests – get_workflow_run
# ---------------------------------------------------------------------------


def test_get_workflow_run():
    from github_actions_mcp.server import get_workflow_run

    expected = {"id": 123, "status": "completed", "conclusion": "success"}
    with _patch_get(expected) as mock_get:
        result = get_workflow_run(run_id=123, owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(f"/repos/{OWNER}/{REPO}/actions/runs/123")
    assert result["conclusion"] == "success"


# ---------------------------------------------------------------------------
# Tests – cancel / rerun
# ---------------------------------------------------------------------------


def test_cancel_workflow_run():
    from github_actions_mcp.server import cancel_workflow_run

    with _patch_post({"status": "ok"}) as mock_post:
        result = cancel_workflow_run(run_id=456, owner=OWNER, repo=REPO)

    mock_post.assert_called_once_with(f"/repos/{OWNER}/{REPO}/actions/runs/456/cancel")
    assert result["status"] == "ok"


def test_rerun_workflow_run_defaults():
    from github_actions_mcp.server import rerun_workflow_run

    with _patch_post({"status": "ok"}) as mock_post:
        result = rerun_workflow_run(run_id=789, owner=OWNER, repo=REPO)

    mock_post.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/runs/789/rerun",
        {"enable_debug_logging": False},
    )
    assert result["status"] == "ok"


def test_rerun_workflow_run_with_debug():
    from github_actions_mcp.server import rerun_workflow_run

    with _patch_post({"status": "ok"}) as mock_post:
        rerun_workflow_run(run_id=789, owner=OWNER, repo=REPO, enable_debug_logging=True)

    args = mock_post.call_args
    assert args[0][1]["enable_debug_logging"] is True


def test_rerun_failed_jobs():
    from github_actions_mcp.server import rerun_failed_jobs

    with _patch_post({"status": "ok"}) as mock_post:
        result = rerun_failed_jobs(run_id=99, owner=OWNER, repo=REPO)

    mock_post.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/runs/99/rerun-failed-jobs",
        {"enable_debug_logging": False},
    )
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests – trigger_workflow
# ---------------------------------------------------------------------------


def test_trigger_workflow_no_inputs():
    from github_actions_mcp.server import trigger_workflow

    with _patch_post({"status": "ok"}) as mock_post:
        result = trigger_workflow(
            workflow_id="deploy.yml", ref="main", owner=OWNER, repo=REPO
        )

    mock_post.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/workflows/deploy.yml/dispatches",
        {"ref": "main"},
    )
    assert result["status"] == "ok"


def test_trigger_workflow_with_inputs():
    from github_actions_mcp.server import trigger_workflow

    with _patch_post({"status": "ok"}) as mock_post:
        trigger_workflow(
            workflow_id="deploy.yml",
            ref="main",
            owner=OWNER,
            repo=REPO,
            inputs={"environment": "prod", "version": "1.2.3"},
        )

    args = mock_post.call_args
    assert args[0][1]["inputs"] == {"environment": "prod", "version": "1.2.3"}


# ---------------------------------------------------------------------------
# Tests – jobs
# ---------------------------------------------------------------------------


def test_list_workflow_jobs():
    from github_actions_mcp.server import list_workflow_jobs

    expected = {
        "total_count": 2,
        "jobs": [
            {"id": 1, "name": "build", "status": "completed", "conclusion": "success"},
            {"id": 2, "name": "test", "status": "completed", "conclusion": "failure"},
        ],
    }
    with _patch_get(expected) as mock_get:
        result = list_workflow_jobs(run_id=100, owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/runs/100/jobs",
        {"filter": "latest", "per_page": 30, "page": 1},
    )
    assert result["total_count"] == 2


def test_get_job():
    from github_actions_mcp.server import get_job

    expected = {"id": 55, "name": "build", "status": "completed"}
    with _patch_get(expected) as mock_get:
        result = get_job(job_id=55, owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(f"/repos/{OWNER}/{REPO}/actions/jobs/55")
    assert result["id"] == 55


# ---------------------------------------------------------------------------
# Tests – logs URLs (redirect handling)
# ---------------------------------------------------------------------------


def test_get_job_logs_url_redirect():
    from github_actions_mcp.server import get_job_logs_url

    logs_location = "https://objects.githubusercontent.com/job-logs.zip"
    redirect = _fake_redirect(logs_location)

    with patch("github_actions_mcp.server._client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = redirect
        mock_client_cls.return_value = mock_client

        result = get_job_logs_url(job_id=55, owner=OWNER, repo=REPO)

    assert result["logs_url"] == logs_location


def test_get_workflow_run_logs_url_redirect():
    from github_actions_mcp.server import get_workflow_run_logs_url

    logs_location = "https://objects.githubusercontent.com/run-logs.zip"
    redirect = _fake_redirect(logs_location)

    with patch("github_actions_mcp.server._client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = redirect
        mock_client_cls.return_value = mock_client

        result = get_workflow_run_logs_url(run_id=100, owner=OWNER, repo=REPO)

    assert result["logs_url"] == logs_location


# ---------------------------------------------------------------------------
# Tests – artifacts
# ---------------------------------------------------------------------------


def test_list_run_artifacts():
    from github_actions_mcp.server import list_run_artifacts

    expected = {"total_count": 1, "artifacts": [{"id": 9, "name": "build-output"}]}
    with _patch_get(expected) as mock_get:
        result = list_run_artifacts(run_id=100, owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/runs/100/artifacts",
        {"per_page": 30, "page": 1},
    )
    assert result["total_count"] == 1


def test_list_repo_artifacts_with_name_filter():
    from github_actions_mcp.server import list_repo_artifacts

    expected = {"total_count": 1, "artifacts": [{"id": 9, "name": "coverage"}]}
    with _patch_get(expected) as mock_get:
        result = list_repo_artifacts(owner=OWNER, repo=REPO, name="coverage")

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/artifacts",
        {"name": "coverage", "per_page": 30, "page": 1},
    )
    assert result["total_count"] == 1


# ---------------------------------------------------------------------------
# Tests – get_run_summary
# ---------------------------------------------------------------------------


def test_get_run_summary():
    from github_actions_mcp.server import get_run_summary

    run_payload = {
        "id": 100,
        "name": "CI",
        "workflow_id": 42,
        "head_branch": "main",
        "head_sha": "abc123",
        "event": "push",
        "status": "completed",
        "conclusion": "success",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:05:00Z",
        "html_url": "https://github.com/test-owner/test-repo/actions/runs/100",
        "run_number": 5,
        "run_attempt": 1,
        "triggering_actor": {"login": "alice"},
    }
    jobs_payload = {
        "total_count": 1,
        "jobs": [
            {
                "id": 1,
                "name": "build",
                "status": "completed",
                "conclusion": "success",
                "started_at": "2024-01-01T00:01:00Z",
                "completed_at": "2024-01-01T00:04:00Z",
                "html_url": "https://github.com/test-owner/test-repo/actions/runs/100/jobs/1",
            }
        ],
    }
    artifacts_payload = {"total_count": 2, "artifacts": []}

    side_effects = [run_payload, jobs_payload, artifacts_payload]

    with patch("github_actions_mcp.server._get", side_effect=side_effects):
        result = get_run_summary(run_id=100, owner=OWNER, repo=REPO)

    assert result["run"]["id"] == 100
    assert result["run"]["conclusion"] == "success"
    assert result["run"]["triggering_actor"] == "alice"
    assert len(result["jobs_summary"]) == 1
    assert result["jobs_summary"][0]["name"] == "build"
    assert result["artifacts_count"] == 2


# ---------------------------------------------------------------------------
# Tests – list_failed_runs
# ---------------------------------------------------------------------------


def test_list_failed_runs_repo_level():
    from github_actions_mcp.server import list_failed_runs

    expected = {"total_count": 3, "workflow_runs": []}
    with _patch_get(expected) as mock_get:
        result = list_failed_runs(owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/runs",
        {"status": "failure", "branch": "", "per_page": 10},
    )
    assert result["total_count"] == 3


def test_list_failed_runs_scoped_to_workflow():
    from github_actions_mcp.server import list_failed_runs

    with _patch_get({"total_count": 1, "workflow_runs": []}) as mock_get:
        list_failed_runs(owner=OWNER, repo=REPO, workflow_id="ci.yml", branch="main")

    mock_get.assert_called_once_with(
        f"/repos/{OWNER}/{REPO}/actions/workflows/ci.yml/runs",
        {"status": "failure", "branch": "main", "per_page": 10},
    )


# ---------------------------------------------------------------------------
# Tests – _resolve helper
# ---------------------------------------------------------------------------


def test_resolve_uses_defaults(monkeypatch):
    from github_actions_mcp import server

    monkeypatch.setattr(server.settings, "default_owner", "default-org")
    monkeypatch.setattr(server.settings, "default_repo", "default-repo")

    owner, repo = server._resolve("", "")
    assert owner == "default-org"
    assert repo == "default-repo"


def test_resolve_explicit_values_override_defaults(monkeypatch):
    from github_actions_mcp import server

    monkeypatch.setattr(server.settings, "default_owner", "default-org")
    monkeypatch.setattr(server.settings, "default_repo", "default-repo")

    owner, repo = server._resolve("explicit-org", "explicit-repo")
    assert owner == "explicit-org"
    assert repo == "explicit-repo"


# ---------------------------------------------------------------------------
# Tests – get_workflow_run_usage
# ---------------------------------------------------------------------------


def test_get_workflow_run_usage():
    from github_actions_mcp.server import get_workflow_run_usage

    expected = {
        "billable": {"UBUNTU": {"total_ms": 120000}},
        "run_duration_ms": 120000,
    }
    with _patch_get(expected) as mock_get:
        result = get_workflow_run_usage(run_id=100, owner=OWNER, repo=REPO)

    mock_get.assert_called_once_with(f"/repos/{OWNER}/{REPO}/actions/runs/100/timing")
    assert result["run_duration_ms"] == 120000
