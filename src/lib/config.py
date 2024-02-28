import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    GHA_TOKEN = os.getenv("GHA_TOKEN", "")
    NEW_RELIC_LICENSE_KEY = os.getenv("NEW_RELIC_LICENSE_KEY", "")
    GHA_RUN_ID = os.getenv("GHA_RUN_ID")
    GHA_SERVICE_NAME = os.getenv("GITHUB_REPOSITORY", "")
    GITHUB_REPOSITORY_OWNER = os.getenv("GITHUB_REPOSITORY_OWNER", "")
    GHA_RUN_NAME = os.getenv("GHA_RUN_NAME")
    GITHUB_API_URL = os.getenv("GITHUB_API_URL", "")
    PARSE_LOGS = os.getenv("PARSE_LOGS", "true").lower() == "true"
    INCLUDE_ID_IN_PARENT_SPAN_NAME = (
        os.getenv("INCLUDE_ID_IN_PARENT_SPAN_NAME", "true").lower() == "true"
    )
    GHA_DEBUG = os.getenv("GHA_DEBUG", "false").lower() == "true"

    @property
    def OTEL_EXPORTER_ENDPOINT(self):  # pylint: disable=invalid-name
        if Config.NEW_RELIC_LICENSE_KEY.startswith("eu"):
            return "https://otlp.eu01.nr-data.net:4318"

        return "https://otlp.nr-data.net"

    @staticmethod
    def check_env_vars():
        required_env_vars = (
            "NEW_RELIC_LICENSE_KEY",
            "GHA_TOKEN",
            "GHA_RUN_ID",
            "GHA_SERVICE_NAME",
            "GITHUB_REPOSITORY_OWNER",
            "GHA_RUN_NAME",
            "GITHUB_API_URL",
        )

        keys_not_set = []

        for env_var in required_env_vars:
            if not getattr(Config, env_var):
                keys_not_set.append(env_var)
        else:
            pass

        if len(keys_not_set) > 0:
            print(f"Missing required environment variables: {keys_not_set}")
            exit(1)
