import json

from ghapi.all import GhApi

from .config import Config
from .custom_parser import do_fastcore_decode, do_time, parse_attributes


class GithubApi:
    def __init__(self):
        self.api = GhApi(
            owner=Config.GITHUB_REPOSITORY_OWNER,
            repo=Config.GHA_SERVICE_NAME.split("/")[1],
            token=Config.GHA_TOKEN,
        )

    def get_workflow_run_by_id(self):
        return do_fastcore_decode(self.api.actions.get_workflow_run(Config.GHA_RUN_ID))

    def get_workflow_run_jobs_by_run_id(self, page=1, jobs=None):
        if jobs is None:
            jobs = []

        try:
            response = do_fastcore_decode(
                self.api.actions.list_jobs_for_workflow_run(
                    Config.GHA_RUN_ID, page=page
                )
            )
            workflow_run = json.loads(response)
            jobs.extend(workflow_run["jobs"])

            if workflow_run["total_count"] > len(jobs):
                return self.get_workflow_run_jobs_by_run_id(page + 1, jobs)
        except Exception as e:
            print("Error getting workflow run jobs", e)

        return jobs

    def get_commits_included_in_workflow_run(self, workflow_run_atts, branch):
        commits = []
        try:
            workflow_runs = do_fastcore_decode(
                self.api.actions.list_workflow_runs_for_repo(
                    branch=branch, event="push", status="completed"
                )
            )
            workflow_runs = json.loads(workflow_runs)["workflow_runs"]

            previous_run_head_sha = next(
                (
                    workflow_runs[index + 1]["head_sha"]
                    for index, run in enumerate(workflow_runs)
                    if run["id"] == workflow_run_atts["id"]
                ),
                None,
            )

            if previous_run_head_sha:
                print(
                    f"Comparing commits between {previous_run_head_sha} and {workflow_run_atts['head_sha']}"
                )
                raw_response = do_fastcore_decode(
                    self.api.repos.compare_commits(
                        owner=Config.GITHUB_REPOSITORY_OWNER,
                        repo=Config.GHA_SERVICE_NAME.split("/")[1],
                        basehead=previous_run_head_sha
                        + "..."
                        + workflow_run_atts["head_sha"],
                    )
                )
                commits = json.loads(raw_response)["commits"]
        except Exception as e:
            print("Error getting commits", e)
            raise e

        return commits
