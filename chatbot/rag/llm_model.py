from langchain_ollama import OllamaLLM

from .vectordb import get_embedding_function, get_embedding_function_ollama
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma

from langchain.chains.history_aware_retriever import create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import MessagesPlaceholder

from django.conf import settings
from dotenv import load_dotenv
import os
import time
import logging

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
llm_ollama = OllamaLLM(model="llama3.1", base_url="http://host.docker.internal:11434")
def get_context(vector_db, query_text, CLOSEST_K_CHUNK: int = 5, SIMILARITY_THRESHOLD: float = 0.5):
    # Search the DB.
    results = vector_db.similarity_search_with_score(query_text, k=CLOSEST_K_CHUNK)

    filtered_results = [
        (doc, score) for doc, score in results if score-1 <= SIMILARITY_THRESHOLD
    ]

    sources = [doc.metadata.get("id", None) for doc, _score in filtered_results]

    if filtered_results:
        context_text = "\n\n---\n\n".join([ doc.page_content for doc,_score in filtered_results])
    else:
        context_text = "There is nothing found in the database as a context."
    # retriever = vector_db.as_retriever(search_kwargs={"k": CLOSEST_K_CHUNK})
    return {"context":context_text, "sources":sources}

    # system_instruction = """Given a chat history and the latest user question \
    #     which might reference context in the chat history, formulate a standalone question \
    #     which can be understood without the chat history. Do NOT answer the question, \
    #     just reformulate it if needed and otherwise return it as is."""
    # # We are navigating retriever to do the relevant searches based on the conversation history
    # retriever_prompt = ChatPromptTemplate.from_messages([
    #     ("system", system_instruction),
    #     MessagesPlaceholder(variable_name="chat_history"),
    #     ("human", "{input}")]
    # )

    # history_aware_retriever = create_history_aware_retriever(
    #     llm=model,
    #     retriever=retriever,
    #     prompt=retriever_prompt
    # )

    # retrieval_results = history_aware_retriever.invoke({
    #     "input": query_text,
    #     "chat_history": chat_history
    # })
    # context_list = []
    # for i, doc in enumerate(retrieval_results):
    #     print(doc)
    # context = "\n\n".join(context_list)
    # print(context)
    # return context

def generate_conversation_name(query: str, response: str) -> str:
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Generate a short, meaningful title (maximum 6 words) for a conversation based on the following query and response. The title should capture the main topic or intent of the conversation. Only return the title, nothing else."),
        ("human", f"Query: {query}\nResponse: {response}")
    ])
    
    try:
        name = llm_ollama.invoke(prompt_template.format())
        # Clean up the name - remove quotes if present and limit length
        name = name.strip('"\'').strip()
        if len(name) > 50:  # Set a reasonable maximum length
            name = name[:47] + "..."
        return name
    except Exception as e:
        print("Error generating conversation name:", e)
        return "New Chat"  # Fallback name

def query_llm(query_text: str, chat_history):
    start_time = time.time()
    
    # Initialize embedding function and DB
    logger.info("Initializing embedding function and ChromaDB...")
    embedding_start = time.time()
    embedding_function = get_embedding_function_ollama()
    db = Chroma(
        persist_directory = settings.CHROMA_PATH,
        embedding_function = embedding_function
    )
    logger.info(f"Embedding initialization took: {time.time() - embedding_start:.2f} seconds")
    
    # Get context
    context_start = time.time()
    context_obj = get_context(db, query_text)
    logger.info(f"Context retrieval took: {time.time() - context_start:.2f} seconds")
    
    # Create prompt
    prompt_start = time.time()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system","The following is the context fetched from the database. Mention your sources if possible in your answer.: \n{context}\n"),
        ("system","The following is a friendly conversation between a human and an AI. If the AI does not know the answer to a question, it truthfully says it does not know."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("system","AI is instructed only to answer the below question using the conversation history and the context.\n"),
        ("human", "{input}"),
        ("ai","")
    ])
    prompt = prompt_template.format(context=context_obj["context"], input=query_text, chat_history=chat_history)
    logger.info(f"Prompt creation took: {time.time() - prompt_start:.2f} seconds")
    
    # LLM inference
    llm_start = time.time()
    try:
        response = llm_ollama.invoke(prompt)
        logger.info(f"LLM inference took: {time.time() - llm_start:.2f} seconds")
    except Exception as e:
        logger.error(f"Error invoking LLM: {str(e)}")
        print("Error invoking chain:", e)
        
    total_time = time.time() - start_time
    logger.info(f"Total query_llm execution time: {total_time:.2f} seconds")
    
    return {"response_text":response, "sources":context_obj["sources"]}