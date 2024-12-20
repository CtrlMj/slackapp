import os
import json
import requests
import cohere
from google.cloud import aiplatform
from google.cloud import firestore
from flask import Response
from flask import jsonify
from urllib.parse import parse_qs
from vertexai.preview.language_models import TextEmbeddingModel

# langchain imports
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain.prompts import PromptTemplate
from langchain.llms import VertexAI
from langchain.chains import LLMChain, HypotheticalDocumentEmbedder
from langchain.embeddings import VertexAIEmbeddings
from langchain.vectorstores.matching_engine import MatchingEngine
from langchain.chains import RetrievalQA
from langchain.chains.question_answering import load_qa_chain
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import Namespace

from utils import read_secret, logger


from grpc import _InactiveRpcError
from typing import Dict, List, Tuple
# Load environment variables

project_id = os.environ['project_id']

# read secrets
COHERE_API_KEY = read_secret('COHERE_API_KEY', project_id)
matching_engine_proj = read_secret('MATCHING_ENGINE_PROJ', project_id)
deployed_index_id = read_secret('VECTORDB_INDEX_ID', project_id)
vector_endpoint_id = read_secret('VECTORDB_ENDPOINT_ID')
firestore_collection = read_secret("FIRESTORE_COLLECTION_NAME")


# Initialize Cohere
os.environ["COHERE_API_KEY"] = COHERE_API_KEY
co = cohere.Client(COHERE_API_KEY)

# Initialize PaLM embedding
PaLM_embedding = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")
langchain_PaLM_embeddings = VertexAIEmbeddings()

# init HyDE
PaLM_llm = VertexAI()
HyDE = HypotheticalDocumentEmbedder.from_llm(PaLM_llm, langchain_PaLM_embeddings, "web_search")

# init langchain vector store
vector_store = MatchingEngine.from_components(
    project_id=matching_engine_proj,
    region="us-central1",
    index_id=deployed_index_id,
    endpoint_id=vector_endpoint_id,
    firestore_collection_name=firestore_collection,
    embedding=langchain_PaLM_embeddings
)

# init rerank compressor
compressor = CohereRerank(top_n=10)

# init question answering chain
QAchain = load_qa_chain(PaLM_llm, chain_type='stuff')


# Initialize AIPlatform
aiplatform.init(project=project_id, location="us-central1")

# Search with langchain
def search(query: str, user_id: str) -> Dict[str, List[Tuple[str, str]]]:
    """Main search logic

    Args:
        query (str): the question sent via chatbot
        user_id (str): id of the user sending the query

    Returns:
        Dict[str, List[Tuple[str, str]]]: A dictionary with a summary answer and a list of references
    """

    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=vector_store.as_retriever(search_kwargs={"k": 100,
                                                                "filter": [Namespace("ids", [user_id], [])]}))

    # Search in the index
    docs = compression_retriever.get_relevant_documents(query)
    
    chat_response = QAchain({"input_documents": docs[:3], "question": query}, return_only_outputs=True)
    # future streaming
    # for c in QAchain.astream:
    #     yield c
    
    # Gather a list of (page_link, excerpt) from the response
    search_output = []
    for item in docs:
        try:
            doc_id = item.metadata['id']
            url, title = item.metadata['url'], item.metadata['title']
            if (title, url) not in search_output:
                search_output.append((title, url))
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error fetching document with ID {doc_id}: {e}")
            continue
        
    return {"chat_response": chat_response, "search_output": search_output}


def main(request: requests.Request) -> Tuple:
    """main request handler

    Args:
        request (requests.Request): incoming request

    Returns:
        Tuple: Tuple of (search resulst, response_code, headers)
    """
        
    logger.info(f"About to search, here is the request data: {request.data}")

    rq_data = request.data.decode()
    parsed_data = json.loads(rq_data)
    query = parsed_data["query"]
    user_id = parsed_data["user_id"]

    try:
        search_results = search(query, user_id)
        if search_results['chat_response'] == "":
            logger.info("Error: (output text is blank)")
        logger.info("Search complete, final results: %s", search_results)
    except _InactiveRpcError:
        logger.info("Error: Likely matching engine cold start")
    
    headers = {
        'Content-Type': 'application/json'
    }

    return (search_results, 200, headers)
