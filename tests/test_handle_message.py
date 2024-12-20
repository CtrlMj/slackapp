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

@pytest.mark.integration
def test_handle_message_feedback(
    mock_db
):
    # Mock request data
    mock_request = MagicMock(spec=Request)
    mock_request.data = b'{"data": {"type": "interactive_message", "callback_id": "feedback_user1_1234", "actions": [{"value": "👍"}]}}'

    # Call the function
    response = handle_message(mock_request)

    # Assertions for feedback
    mock_db.collection.assert_called_with("slackbot_feedback")
    mock_db.collection().document.assert_called_with("user1_1234")
    mock_db.collection().document().update.assert_called_with({"feedback": 1})
    assert response == ("OK", 200)

@pytest.mark.integration
def test_handle_message_showmore(
    mock_r, mock_client
):
    # Mock Redis data
    mock_r.hgetall.return_value = {
        b"search_results.3": b"Title1$$$http://link1",
        b"search_results.4": b"Title2$$$http://link2",
    }

    # Mock request data
    mock_request = MagicMock(spec=Request)
    mock_request.data = b'{"data": {"type": "interactive_message", "callback_id": "user1_1234", "user": {"id": "user1"}}}'

    # Call the function
    response = handle_message(mock_request)

    # Assertions for show more
    mock_r.hgetall.assert_called_with("slackbot_showmore:user1_1234")
    mock_client.chat_postMessage.assert_any_call(
        channel="user1",
        attachments=[
            {
                "fallback": "Your search results are ready!",
                "color": "#DBB0CE",
                "title": "Title1",
                "title_link": "http://link1",
            }
        ],
    )
    assert response == ("OK", 200)

@pytest.mark.integration
def test_handle_message_initial_message(
    mock_client, mock_id_token, mock_requests
):
    # Mock request data
    mock_request = MagicMock(spec=Request)
    mock_request.data = b'{"data": {"type": "initial_message", "text": "search query", "user": "user1", "ts": "1234"}}'

    # Mock search response
    mock_requests.return_value.text = json.dumps(
        {
            "chat_response": {"output_text": "Here are your results."},
            "search_output": [
                ["Title1", "http://link1"],
                ["Title2", "http://link2"],
                ["Title3", "http://link3"],
            ],
        }
    )

    # Mock token
    mock_id_token.fetch_id_token.return_value = "mock_token"

    # Call the function
    response = handle_message(mock_request)

    # Assertions for initial message
    mock_requests.assert_called_once()
    mock_client.chat_postMessage.assert_any_call(
        channel="user1", text="*Here are your results.*"
    )
    mock_client.chat_postMessage.assert_any_call(
        channel="user1",
        attachments=[
            {
                "fallback": "Your search results are ready!",
                "color": "#DBB0CE",
                "title": "Title1",
                "title_link": "http://link1",
            }
        ],
    )
    assert response == ("OK", 200)
