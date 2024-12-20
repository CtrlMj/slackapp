import base64
import json
import os
import requests
import urllib
import google.auth
import google.oauth2.id_token
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from slack_sdk import WebClient
from google.cloud import pubsub_v1
from time import time
from typing import Tuple
from google.cloud import firestore
import redis
from grpc import _InactiveRpcError
from utils import read_secret, logger
# Load environment variables
project_id = os.environ['project_id']

# Firestore initialization
try:
    db = firestore.Client()
    logger.info("Firestore DB initialized.")
except ValueError:
    pass


# Redis client init
pswrd = read_secret("REDIS_PASS", project_id)
port = read_secret("REDIS_PORT", project_id)
host = read_secret("REDIS_HOST", project_id)
r = redis.Redis(host=host, port=port, password=pswrd)

# read search logic url:
search_func_url = read_secret('search_func_url', project_id)

# Initialize WebClient
bot_api_token = read_secret('BOT_TOKEN', project_id)
client = WebClient(token=bot_api_token)
def handle_message(request: requests.Request) -> Tuple[str, int]:
    """
    Receive request from pubsub and either calls the search logic for response
    or returns feedback or showmore buttons

    Args:
        request (requests.Request): request object from pubsub function

    Returns:
        Tuple[str, int]: response string and code
    """
    logger.info("Here is the event: %s", request.data)
    pre_event_data = request.data.decode('utf-8')
    event_data = json.loads(pre_event_data)

    logger.info("Event Data: %s", event_data)
     
    data_dict = event_data['data']

    # Initialize message colors:
    colours = ['#DBB0CE', '#411C50', '#E99E86']
    colour_counter = 0

    # check if interactive message (either feedback or showmore button):
    if data_dict['type'] == "interactive_message":
        if data_dict['callback_id'].startswith("feedback"):
            user_id, ts = data_dict['callback_id'].split("_")[1:]
            feedback = data_dict['actions'][0]['value']
            if feedback == "👍":
                feedback = 1
            elif feedback == "👎":
                feedback = -1
            db.collection("slackbot_feedback").document(f"{user_id}_{ts}").update({f"feedback": feedback})
        else:
            user_id = data_dict['user']['id']
            # Retrieve rest of the search results
            search_results = r.hgetall(f"slackbot_showmore:{data_dict['callback_id']}")
            search_output = [(v.decode('utf-8').split('$$$')[0], v.decode('utf-8').split('$$$')[1]) for v in search_results.values()]
            for i in range(3, len(search_output)):
                logger.info(f"attempting to post the {i}th message")
                client.chat_postMessage(
                    channel=user_id,
                    attachments=[
                        {
                            'fallback': "Your search results are ready!",
                            'color': colours[colour_counter % 3],
                            'title': search_output[i][0],
                            'title_link': search_output[i][1]
                        }
                    ],
                )
                colour_counter += 1
    
    # if not an interactive message then it's the first question
    else:
        text = data_dict['text']
        user_id = data_dict['user']
        ts = data_dict['ts']
        logger.info("processing request %s for user %s", text, user_id)
    
        data = {'query': text, 'user_id': event_data['user_id']}

        id_token_info = id_token.fetch_id_token(Request(), search_func_url)
        headers = {'Content-type': 'application/json', 
                   'Authorization': f'Bearer {id_token_info}'}
        try:
            logger.info("Pulling search data.")
            response = requests.post(search_func_url, json=data, headers=headers)
            response_list = json.loads(response.text)
            if response_list['chat_response']['output_text'] == "":
                client.chat_postMessage(channel=user_id, text="*I don't know.*")
                logger.info("Search data pulled")
        except _InactiveRpcError:
            client.chat_postMessage(channel=user_id, text="*Sorry, we encountered an error. Your query has been logged for analysis.*")
            return "QUERY ERROR", 404

        response_list = json.loads(response.text)
        logger.info("Response list: %s", response_list)

        unformatted_chat_response = response_list['chat_response']['output_text']
        chat_response_lines = unformatted_chat_response.split('\n')  # split the text into lines
        chat_response_lines_bold = [f"*{line}*" if line.strip() else line for line in chat_response_lines]  # make each non-empty line bold
        chat_response = '\n'.join(chat_response_lines_bold)  # join the lines back together
        if chat_response == "": # 'I don't know' has already been posted, no need to post any other text besides the links
            pass
        else:
            client.chat_postMessage(channel=user_id, text=chat_response)
            # future adding history:
            # history = r.hget(f"slackbot_showmore:{user_id}_{ts}", "history")
            # r.hset(f"slackbot_showmore:{user_id}_{ts}", "history", f"{chat_response + history}")

        search_output = response_list['search_output']
        # store search output in cache
        for i, item in enumerate(search_output):
            r.hset(f"slackbot_showmore:{user_id}_{ts}", 
                   f"search_results.{i}", f"{item[0]}$$${item[1]}")
        
        # send the messages
        for i in range(3):
            client.chat_postMessage(
                channel=user_id,
                attachments=[
                    {
                        'fallback': "Your search results are ready!",
                        'color': colours[colour_counter % 3],
                        'title': search_output[i][0],
                        'title_link': search_output[i][1]
                    }
                ],
            )
            colour_counter += 1

        # Show More button
        logger.info("Posting show more button...")
        client.chat_postMessage(
            channel=user_id,
            attachments=[
                {   
                    "text": "Need more results?",
                    "color": "#3AA3E3",  # Might want to remove this line depending on how we want UI to look
                    "attachment_type": "default",
                    "callback_id": f"{user_id}_{ts}",
                    "actions": [
                        {
                            "name": "show_more",
                            "text": "Show More",
                            "type": "button",
                            "value": "showmore"
                        },
                    ],
                }
            ]
        )

        # Post thumbs up and down buttons
        client.chat_postMessage(
            channel=user_id,
            attachments=[
                {
                    "text": "How did I do?",
                    "attachment_type": "default",
                    "callback_id": f"feedback_{user_id}_{ts}",
                    "actions": [
                        {
                            "name": "thumbs_up",
                            "text": "👍",
                            "type": "button",
                            "value": "👍"
                        },
                        {
                            "name": "thumbs_down",
                            "text": "👎",
                            "type": "button",
                            "value": "👎"
                        }
                    ]
                }
            ]
        )

    return 'OK', 200