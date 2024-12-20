from google.cloud import secretmanager
import logging
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.cloud import logging as cloud_logging

# Initialize Google Cloud Logging client
client = cloud_logging.Client()
# intialize secret manager
secret_manager_client = secretmanager.SecretManagerServiceClient()
def read_secret(secret_id: str, project_id: str) -> str:
    """fetches secret value from secert manager

    Args:
        secret_id (str): id of the target secret
        project_id (str): id of the project

     Returns:
        str: secert value
    """
    secret_name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = secret_manager_client.access_secret_version(request={"name": secret_name})
    secret_value = response.payload.data.decode("UTF-8")
    return secret_value

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "minimal": {"format": "%(message)s"},
        "detailed": {
            "format": "%(levelname)s %(asctime)s [%(name)s:%(filename)s:%(funcName)s:%(lineno)d]\n%(message)s\n"
        },
    },
    "handlers": {
        "cloud": {
            "class": "google.cloud.logging_v2.handlers.CloudLoggingHandler",
            "client": client,
            "formatter": "detailed",
            "level": logging.INFO,
        },
    },
    "root": {
        "handlers": ["cloud"],
        "level": logging.INFO,
        "propagate": True,
    },
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger()
