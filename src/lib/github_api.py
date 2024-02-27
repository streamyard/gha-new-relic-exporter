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
