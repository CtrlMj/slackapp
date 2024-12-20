import os
import json
import slack_sdk
from flask import request, jsonify
from slack_sdk.signature import SignatureVerifier
from google.cloud import pubsub_v1
from google.cloud import firestore
from urllib.parse import parse_qs
from utils import read_secret, logger
# Load environment variables
project_id = os.environ['GCP_PROJECT']

# read secrets
topic_id = read_secret('PUBSUB_TOPIC', project_id)
slackapp_id = read_secret('SLACK_APP_ID', project_id)
# Initialize Pub/Sub client
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_id)


def publish(request):
    if request.mimetype == "application/x-www-form-urlencoded":
        data = dict(request.form)
        logger.info(f"this is the urlencoded form: {data}")
        # Publish message to topic
        data = json.dumps(data['payload']).encode("utf-8")
        future = publisher.publish(topic_path, data=data)

        # Wait for Pub/Sub acknowledgement
        try:
            message_id = future.result()
            print(f"Published message with ID: {message_id}")
            return 'OK', 200
            
        except Exception as e:
            logger.error(f"An error occurred while publishing the message: {e}")
            return 'Internal Server Error', 500
        
    elif request.mimetype == 'application/json':
        logger.info(f"Here's the json request: {request.json}")
        # Ensure request is POST
        if request.method != 'POST':
            logger.warning("Request is not POST.")
            return 'Method not allowed', 405

        print("Ensured request is POST.")
        data = request.json
        # Double check request data --> may not be necessary
        if not data:
            logger.warning("No data in request.")
            return 'Invalid request', 400
        # Check if request requires challenge parameter for request URL verification
        if data.get('type') == 'url_verification':
            logger.info(f"Verifying URL for Slack acceptance: {data}")
            return jsonify({'challenge': data.get('challenge')}), 200
       
        # Get app ID info
        app_id = str(data.get('api_app_id'))

        # Figure out which app specific tokens to use
        if app_id == slackapp_id:
            signing_secret = read_secret('SIGNING_SECRET_SLACK', project_id)
            ver_token = read_secret('VERIFICATION_TOKEN_SLACK', project_id)
            bot_api_token = read_secret('BOT_TOKEN_SLACK', project_id)
        else:
            raise ValueError("No logic exists for that app.")

        # Load bot ID
        client = slack_sdk.WebClient(token=bot_api_token)
        bot_id = client.api_call("auth.test")['user_id']

        # Initialize signature verifier
        signature_verifier = SignatureVerifier(signing_secret)

        # Ensure Slack request is valid 
        if not signature_verifier.is_valid_request(request.get_data(), request.headers):
            logger.error("Signature error.")
            return jsonify({'error': 'invalid_request'}), 400

        # Check Slack verification token
        if data.get('token') != ver_token:
            logger.error(f"Invalid Slack verification token: {data}")
            return 'Invalid request, bad token', 400

        # Get event info
        event = data.get('event')
        user_id = event.get('user')

        # Ensure bot is not reading its own messages
        if user_id != bot_id:
            if event and event.get("type") == "message" and event.get("channel_type") == "im":
                # Create a Pub/Sub message with the event data
                message = json.dumps(event).encode("utf-8")
                
                # Publish message to topic
                future = publisher.publish(topic_path, data=message, app_id=app_id)

                # Wait for Pub/Sub acknowledgement
                try:
                    message_id = future.result()
                    logger.info(f"Published message with ID: {message_id}")
                    return 'OK', 200
                    
                except Exception as e:
                    logger.error(f"An error occurred while publishing the message: {e}")
                    return 'Internal Server Error', 500

        return 'Bad Request', 400
    
    else:
        raise TypeError("Unrecognized request mimetype!")

    

    


    

   

    

    

    
