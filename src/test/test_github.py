import json
from unittest.mock import patch

from lib.config import Config
from lib.github_api import GithubApi


## We're going to mock the requests that are made to the github api that
## are used by GhApi in the GithubApi class
class TestGithubApi:
    @patch("lib.github_api.GhApi")
    def test_get_workflow_run_by_id(self, mock_GhApi):
        Config.GHA_RUN_ID = 123  # pyright: ignore
        mock_GhApi.return_value.actions.get_workflow_run.return_value = {
            "id": "some_workflow"
        }
        api = GithubApi()
        assert api.get_workflow_run_by_id() == json.dumps({"id": "some_workflow"})
        mock_GhApi.return_value.actions.get_workflow_run.assert_called_once_with(123)

    @patch("lib.github_api.GhApi")
    def test_get_workflow_run_jobs_by_run_id(self, mock_GhApi):
        Config.GHA_RUN_ID = 123  # pyright: ignore
        mock_GhApi.return_value.actions.list_jobs_for_workflow_run.return_value = {
            "jobs": ["job1", "job2"],
            "total_count": 2,
        }
        api = GithubApi()
        res = api.get_workflow_run_jobs_by_run_id()
        assert res == ["job1", "job2"]
        mock_GhApi.return_value.actions.list_jobs_for_workflow_run.assert_called_once_with(
            123, page=1
        )

    @patch("lib.github_api.GhApi")
    def test_get_commits_included_in_workflow_run(self, mock_GhApi):
        mock_GhApi.return_value.actions.list_workflow_runs_for_repo.return_value = {
            "workflow_runs": [
                {"head_sha": "sha1", "id": 1},
                {"head_sha": "sha2", "id": 2},
            ]
        }
        mock_GhApi.return_value.repos.compare_commits.return_value = {
            "commits": ["sha2"]
        }
        api = GithubApi()
        res = api.get_commits_included_in_workflow_run(
            {"id": 1, "head_sha": "sha1"}, "some_branch"
        )
        assert res == ["sha2"]
        mock_GhApi.return_value.actions.list_workflow_runs_for_repo.assert_called_once_with(
            branch="some_branch", event="push", status="completed"
        )
        mock_GhApi.return_value.repos.compare_commits.assert_called_once_with(
            owner=Config.GITHUB_REPOSITORY_OWNER,
            repo=Config.GHA_SERVICE_NAME.split("/")[1],
            basehead="sha2...sha1",
        )
