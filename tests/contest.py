import pytest
from unittest.mock import MagicMock, patch
import json
from typing import Tuple
from requests import Request
from cloudfunctions.handle_messages.handle_message import handle_message  # Replace with the actual module name


@pytest.fixture
def mock_logger():
    with patch("cloudfunctions.handle_messages.handle_message.logger") as logger:
        yield logger


@pytest.fixture
def mock_db():
    with patch("cloudfunctions.handle_messages.handle_message.db") as db:
        yield db


@pytest.fixture
def mock_r():
    with patch("cloudfunctions.handle_messages.handle_message.r") as r:
        yield r


@pytest.fixture
def mock_client():
    with patch("cloudfunctions.handle_messages.handle_message.client") as client:
        yield client


@pytest.fixture
def mock_id_token():
    with patch("cloudfunctions.handle_messages.handle_message.id_token") as id_token:
        yield id_token


@pytest.fixture
def mock_requests():
    with patch("cloudfunctions.handle_messages.handle_message.requests.post") as requests_post:
        yield requests_post