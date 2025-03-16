from langchain_ollama import OllamaLLM

from .vectordb import get_embedding_function, get_embedding_function_ollama
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate

from langchain_core.runnables import chain
from langchain_core.prompts import MessagesPlaceholder

from django.conf import settings
from dotenv import load_dotenv
import os
import time
import logging

from sentence_transformers import CrossEncoder
from langchain_community.document_transformers import LongContextReorder

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

hf_key = os.getenv("HuggingFace_KEY")
#repo_id = "mistralai/Mixtral-8x7B-Instruct-v0.1"
repo_id = "mistralai/Mistral-7B-Instruct-v0.3"
#repo_id ="Qwen/Qwen2.5-72B-Instruct"
# TODO: Needs to be set in the admin panel
# closer to 0 -> more relevant yet lesser results
#SIMILARITY_THRESHOLD = 0.4

# TODO: Needs to be set in the admin panel
#CLOSEST_K_CHUNK = 5
'''
model = HuggingFaceEndpoint(
        repo_id=repo_id,
        temperature=0.5,
        model_kwargs={"max_length": 128},
        huggingfacehub_api_token=hf_key,
    )
'''


'''
# To run on local machine with Ollama (ollama needs to be installed)
from langchain_ollama import OllamaLLM
'''

model_name = os.getenv("MODEL_NAME")
# model_name = "deepseek-r1:8b"
llm_ollama = OllamaLLM(model=model_name, base_url="http://host.docker.internal:11434")


@chain
def get_context(chain_object, CLOSEST_K_CHUNK: int = 100, OUTPUT_M_CHUNK: int = 10, SIMILARITY_THRESHOLD: float = 0):
    # Retrieve candidate chunks using the bi-encoder method.
    results = chain_object["vector_db"].similarity_search_with_score(chain_object["query_text"], k=CLOSEST_K_CHUNK)

    # Prepare pairs for cross-encoder: (query, candidate page_content)
    pairs = [(chain_object["query_text"], doc.page_content) for doc, _ in results]

    # Initialize the cross-encoder (local model)
    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")

    # Get cross-encoder scores for each candidate.
    ce_scores = cross_encoder.predict(pairs)

    # Combine the bi-encoder results with cross-encoder scores and sort them.
    # Each element is ((doc, bi_score), ce_score)
    ranked = sorted(zip(results, ce_scores), key=lambda x: x[1], reverse=True)

    print("Length of ranked orders:", len(ranked))

    # Filter candidates based on the SIMILARITY_THRESHOLD using the cross-encoder score.
    filtered_rank = [item for item in ranked if item[1] >= SIMILARITY_THRESHOLD]

    # Select the top candidates from those that pass the threshold.
    top_rank = filtered_rank[:OUTPUT_M_CHUNK]

    # Reordering Step using LongContextReorder
    reorderer = LongContextReorder()
    # Extract the texts from the top_rank candidates.
    top_texts = [doc.page_content for ((doc, _), _) in top_rank]
    # Reorder the texts using the LongContextReorder.
    ordered_texts = reorderer.transform_documents(top_texts)

    # Reorder the sources according to the new order of texts.
    ordered_sources = []
    for ot in ordered_texts:
        for ((doc, _), _) in top_rank:
            if doc.page_content == ot:
                ordered_sources.append(doc.metadata.get("id", None))
                break

    # Build the context text from the reordered texts.
    context_text = "\n\n---\n\n".join(ordered_texts)

    # If no candidates were found, use a fallback message.
    if not top_rank:
        context_text = "There is nothing found in the database as a context."

    return {"context": context_text, "sources": ordered_sources}

def generate_conversation_name(query: str, response: str) -> str:
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Generate a short, meaningful title (maximum 6 words) for a conversation based on the following query and response. The title should capture the main topic or intent of the conversation. Only return the title, nothing else."),
        ("human", f"{query}"),
        ("ai", f"{response}")
    ])
    
    try:
        chain = prompt | llm_ollama
        name = chain.invoke({"query":query, "response":response})
        # Clean up the name - remove quotes if present and limit length
        name = name.strip('"\'').strip()
        if len(name) > 50:  # Set a reasonable maximum length
            name = name[:47] + "..."
        return name
    except Exception as e:
        print("Error generating conversation name:", e)
        return "New Chat"  # Fallback name


def query_llm(query_text: str, chat_history):
    
    embedding_function = get_embedding_function_ollama()
    vector_db = Chroma(
        persist_directory = settings.CHROMA_PATH,
        embedding_function = embedding_function
    )
    
    # Get context
    context_obj = get_context.invoke({"vector_db":vector_db, "query_text":query_text})
    
    # Create prompt
    prompt= ChatPromptTemplate.from_messages([
        ("system","The following is the context fetched from the database. Mention your sources if possible in your answer.: \n{context}\n"),
        ("system","The following is a friendly conversation between a human and an AI. If the AI does not know the answer to a question, it truthfully says it does not know."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("system","AI is instructed only to answer the below question using the conversation history and the context.\n"),
        ("human", "{input}"),
        ("ai","")
    ])    
    
    chain = prompt | llm_ollama

    llm_start = time.time()
    try:
        response = chain.invoke({"input":query_text, "context":context_obj["context"], "chat_history":chat_history})
        logger.info(f"LLM invoke call took: {time.time() - llm_start:.1f} seconds")
    except Exception as e:
        print("Error invoking chain:", e)
        
    return {"response_text":response, "sources": context_obj["sources"]}