import os
import zipfile

import requests
from opentelemetry.trace import Status, StatusCode

from .config import Config


def download_log_files():
    bearer = "Bearer " + Config.GHA_TOKEN
    req_headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + Config.GHA_TOKEN,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url1 = (
        Config.GITHUB_API_URL
        + "/repos/"
        + Config.GHA_SERVICE_NAME.split("/")[0]
        + "/"
        + Config.GHA_SERVICE_NAME.split("/")[1]
        + "/actions/runs/"
        + str(Config.GHA_RUN_ID)
        + "/logs"
    )
    r1 = requests.get(url1, headers=req_headers)
    with open("log.zip", "wb") as output_file:
        output_file.write(r1.content)

    with zipfile.ZipFile("log.zip", "r") as zip_ref:
        zip_ref.extractall("./logs")


def parse_log_files(job, step, child_0, child_1, job_logger, logging, dp):
    try:
        with open(
            "./logs/"
            + str(job["name"])
            + "/"
            + str(step["number"])
            + "_"
            + str(step["name"].replace("/", ""))
            + ".txt"
        ) as f:
            for line in f.readlines():
                try:
                    line_to_add = line[29:-1].strip()
                    len_line_to_add = len(line_to_add)
                    timestamp_to_add = line[0:23]
                    if len_line_to_add > 0:
                        # Convert ISO 8601 to timestamp
                        try:
                            parsed_t = dp.isoparse(timestamp_to_add)
                        except ValueError as e:
                            print("Line does not start with a date. Skip for now")
                            continue
                        unix_timestamp = parsed_t.timestamp() * 1000
                        if line_to_add.lower().startswith("##[error]"):
                            child_1.set_status(
                                Status(
                                    StatusCode.ERROR,
                                    line_to_add[9:],
                                )
                            )
                            child_0.set_status(
                                Status(
                                    StatusCode.ERROR,
                                    "STEP: " + str(step["name"]) + " failed",
                                )
                            )
                            job_logger._log(
                                level=logging.ERROR,
                                msg=line_to_add,
                                extra={
                                    "log.timestamp": unix_timestamp,
                                    "log.time": timestamp_to_add,
                                },
                                args="",
                            )
                        elif line_to_add.lower().startswith("##[warning]"):
                            job_logger._log(
                                level=logging.WARNING,
                                msg=line_to_add,
                                extra={
                                    "log.timestamp": unix_timestamp,
                                    "log.time": timestamp_to_add,
                                },
                                args="",
                            )
                        elif line_to_add.lower().startswith("##[notice]"):
                            # Notice (notice): applies to normal but significant conditions that may require monitoring.
                            # Applying INFO4 aka 12 -> https://opentelemetry.io/docs/specs/otel/logs/data-model/#displaying-severity
                            job_logger._log(
                                level=12,
                                msg=line_to_add,
                                extra={
                                    "log.timestamp": unix_timestamp,
                                    "log.time": timestamp_to_add,
                                },
                                args="",
                            )
                        elif line_to_add.lower().startswith("##[debug]"):
                            job_logger._log(
                                level=logging.DEBUG,
                                msg=line_to_add,
                                extra={
                                    "log.timestamp": unix_timestamp,
                                    "log.time": timestamp_to_add,
                                },
                                args="",
                            )
                        else:
                            job_logger._log(
                                level=logging.INFO,
                                msg=line_to_add,
                                extra={
                                    "log.timestamp": unix_timestamp,
                                    "log.time": timestamp_to_add,
                                },
                                args="",
                            )

                except Exception as e:
                    print("Error exporting log line ERROR: ", e)
    except IOError as e:
        if step["conclusion"] == "skipped" or step["conclusion"] == "cancelled":
            print(
                "Log file not expected for this step ->",
                step["name"],
                "<- because its status is ->",
                step["conclusion"],
            )
            pass  # We don't expect log file to exist
        else:
            print(
                "ERROR: Log file does not exist: "
                + str(job["name"])
                + "/"
                + str(step["number"])
                + "_"
                + str(step["name"].replace("/", ""))
                + ".txt"
            )
