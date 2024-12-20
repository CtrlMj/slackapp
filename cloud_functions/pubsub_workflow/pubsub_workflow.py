from google.cloud import workflows_v1
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1 import Execution
from google.cloud.workflows.executions_v1.types import executions
import base64
import json

# Set up API clients
execution_client = executions_v1.ExecutionsClient()
workflows_client = workflows_v1.WorkflowsClient()

project_id = 'prj-s-slackapp-fadb'  
location = 'us-central1'
workflow = 'slackbot-flow'

# Construct the fully qualified location path.
parent = workflows_client.workflow_path(project_id, location, workflow)

def pub_sub_acknowledge_and_trigger_workflow(request):
    print("take a look at the request type:", request.mimetype)
    pub_sub_message = request.get_json()
    # Decode the data and get the app_id
    decoded_data = base64.b64decode(pub_sub_message['message']['data']).decode().strip()
    print("take a look at the decoded data", decoded_data)
    while type(decoded_data) == str:
        decoded_data = json.loads(decoded_data)
    print(type(decoded_data), decoded_data)
    if decoded_data['type'] == 'message':
        app_id = pub_sub_message['message']['attributes']['app_id']
        print("APP_ID: ", app_id)
    elif decoded_data['type'] == 'interactive_message':
        app_id = decoded_data['original_message']['app_id']
        print("APP_ID: ", app_id)
    else:
        raise TypeError("Unrecognized message type!")
    
    
    # Pass the data and app_id to the workflow
    body = json_format.ParseDict({'data': decoded_data, 'app_id': app_id}, Value())

    try:
        print("i got before execution")
        response = execution_client.create_execution(request={"parent": parent, "execution": {"argument": json_format.MessageToJson(body)}})
        print(f'Workflow executed with name: {response.name}')
        return "OK", 200
    except Exception as e:
        print(e)
        return str(e), 500
