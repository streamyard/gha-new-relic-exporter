import json
import logging

import dateutil.parser as dp
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from lib.config import Config
from lib.custom_parser import do_time, parse_attributes
from lib.github_api import GithubApi
from lib.log_parser import download_log_files, parse_log_files
from lib.otel import create_resource_attributes, get_logger, get_tracer

# Check if compulsory env variables are configured
Config.check_env_vars()
api = GithubApi()

# Configure env variables
# Check if debug is set
if Config.GHA_DEBUG:
    print("Running on DEBUG mode")
    import http.client as http_client

    http_client.HTTPConnection.debuglevel = 1
    LoggingInstrumentor().instrument(set_logging_format=True, log_level=logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)
else:
    pass

if Config.PARSE_LOGS:
    download_log_files()

endpoint = "{}".format(Config().OTEL_EXPORTER_ENDPOINT)
headers = "api-key={}".format(Config.NEW_RELIC_LICENSE_KEY)

# Set OTEL resources
global_attributes = {
    SERVICE_NAME: Config.GHA_SERVICE_NAME,
    "workflow_run_id": Config.GHA_RUN_ID,
    "github.source": "github-exporter",
    "github.resource.type": "span",
}


# Ensure we don't export data for new relic exporters
workflow_jobs = api.get_workflow_run_jobs_by_run_id()
workflow_run_finish_time = None
job_lst = []
for job in workflow_jobs:
    if str(job["name"]).lower() not in ["new-relic-exporter"]:
        job_lst.append(job)

if len(job_lst) == 0:
    print(
        "No data to export, assuming this github action workflow job is a new relic exporter"
    )
    exit(0)

workflow_run_atts = json.loads(api.get_workflow_run_by_id())
atts = parse_attributes(workflow_run_atts, "", "workflow")
first_job = job_lst[0] if job_lst else {}
global_attributes["head_branch"] = first_job.get("head_branch", "unknown")
commits_included = api.get_commits_included_in_workflow_run(
    workflow_run_atts, global_attributes["head_branch"]
)

if commits_included:
    global_attributes["commit_count"] = len(commits_included)

print(
    "Processing Workflow ->",
    Config.GHA_RUN_NAME,
    "run id ->",
    Config.GHA_RUN_ID,
)

PARENT_SPAN_NAME = str(Config.GHA_RUN_NAME)
if Config.INCLUDE_ID_IN_PARENT_SPAN_NAME:
    PARENT_SPAN_NAME = PARENT_SPAN_NAME + " - run: " + str(Config.GHA_RUN_ID)

# Set workflow level tracer and logger
global_resource = Resource(attributes=global_attributes)
tracer = get_tracer(endpoint, headers, global_resource, "tracer")

# Trace parent
p_parent = tracer.start_span(
    name=PARENT_SPAN_NAME,
    attributes=atts,
    start_time=do_time(workflow_run_atts["run_started_at"]),
    kind=trace.SpanKind.SERVER,
)

# Jobs trace span
# Set Jobs tracer and logger
pcontext = trace.set_span_in_context(p_parent)
for job in job_lst:
    try:
        print("Processing job ->", job["name"])
        child_0 = tracer.start_span(
            name=str(job["name"]),
            context=pcontext,
            start_time=do_time(job["started_at"]),
            kind=trace.SpanKind.CONSUMER,
        )
        child_0.set_attributes(
            create_resource_attributes(  # pyright: ignore
                parse_attributes(job, "steps", "job"), Config.GHA_SERVICE_NAME
            )
        )
        p_sub_context = trace.set_span_in_context(child_0)

        # Steps trace span
        for index, step in enumerate(job["steps"]):
            try:
                print("Processing step ->", step["name"], "from job", job["name"])
                # Set steps tracer and logger
                resource_attributes = {
                    SERVICE_NAME: Config.GHA_SERVICE_NAME,
                    "github.source": "github-exporter",
                    "github.resource.type": "span",
                    "workflow_run_id": Config.GHA_RUN_ID,
                }
                resource_log = Resource(attributes=resource_attributes)
                step_tracer = get_tracer(endpoint, headers, resource_log, "step_tracer")

                resource_attributes.update(
                    create_resource_attributes(
                        parse_attributes(step, "", "step"),
                        Config.GHA_SERVICE_NAME,
                    )
                )
                resource_log = Resource(attributes=resource_attributes)
                job_logger = get_logger(endpoint, headers, resource_log, "job_logger")

                if step["conclusion"] == "skipped" or step["conclusion"] == "cancelled":
                    if index >= 1:
                        # Start time should be the previous step end time
                        step_started_at = job["steps"][index - 1]["completed_at"]
                    else:
                        step_started_at = job["started_at"]
                else:
                    step_started_at = step["started_at"]

                child_1 = step_tracer.start_span(
                    name=str(step["name"]),
                    start_time=do_time(step_started_at),
                    context=p_sub_context,
                    kind=trace.SpanKind.CONSUMER,
                )
                child_1.set_attributes(
                    create_resource_attributes(  # pyright: ignore
                        parse_attributes(step, "", "job"),
                        Config.GHA_SERVICE_NAME,
                    )
                )
                with trace.use_span(child_1, end_on_exit=False):
                    # Parse logs
                    if Config.PARSE_LOGS:
                        parse_log_files(
                            job, step, child_0, child_1, job_logger, logging, dp
                        )

                if step["conclusion"] == "skipped" or step["conclusion"] == "cancelled":
                    child_1.update_name(name=str(step["name"] + "-SKIPPED"))
                    if index >= 1:
                        # End time should be the previous step end time
                        step_completed_at = job["steps"][index - 1]["completed_at"]
                    else:
                        step_completed_at = job["started_at"]
                else:
                    step_completed_at = step["completed_at"]

                child_1.end(end_time=do_time(step_completed_at))
                print(
                    "Finished processing step ->", step["name"], "from job", job["name"]
                )
            except Exception as e:
                print("Unable to process step ->", step["name"], "<- due to error", e)

        child_0.end(end_time=do_time(job.get("completed_at")))

        workflow_run_finish_time = do_time(job.get("completed_at"))

        print("Finished processing job ->", job.get("name"))
    except Exception as e:
        print("Unable to process job:", job["name"], "<- due to error", e)

p_parent.end(
    end_time=(
        workflow_run_finish_time
        if workflow_run_finish_time
        else do_time(workflow_run_atts["updated_at"])
    )
)
print(
    "Finished processing Workflow ->",
    Config.GHA_RUN_NAME,
    "run id ->",
    Config.GHA_RUN_ID,
)
print("All data exported to New Relic")
