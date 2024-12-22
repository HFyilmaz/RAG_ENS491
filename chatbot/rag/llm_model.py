from .vectordb import get_embedding_function
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

# Load environment variables
load_dotenv()


hf_key = os.getenv("HuggingFace_KEY")
repo_id = "mistralai/Mixtral-8x7B-Instruct-v0.1"
#repo_id ="Qwen/Qwen2.5-72B-Instruct"
# TODO: Needs to be set in the admin panel
# closer to 0 -> more relevant yet lesser results
#SIMILARITY_THRESHOLD = 0.4

# TODO: Needs to be set in the admin panel
#CLOSEST_K_CHUNK = 5
model = HuggingFaceEndpoint(
        repo_id=repo_id,
        temperature=0.5,
        model_kwargs={"max_length": 128},
        huggingfacehub_api_token=hf_key,
    )

def get_context(vector_db, query_text, CLOSEST_K_CHUNK: int = 3, SIMILARITY_THRESHOLD: float = 0.3):
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

def query_llm(query_text: str, chat_history):
    embedding_function = get_embedding_function()
    db = Chroma(
        persist_directory = settings.CHROMA_PATH,
        embedding_function = embedding_function
    )
    
    context_obj = get_context(db, query_text)
    prompt_template = ChatPromptTemplate.from_messages([
        ("system","The following is the context fetched from the database. Mention your sources if possible in your answer.: \n{context}\n"),
        ("system","The following is a friendly conversation between a human and an AI. If the AI does not know the answer to a question, it truthfully says it does not know."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("system","AI is instructed only to answer the below question using the conversation history and the context.\n"),
        ("human", "{input}"),
        ("ai","")
    ])
    prompt= prompt_template.format(context=context_obj["context"], input=query_text, chat_history=chat_history)
    # Directing the prompt to the model
    print(prompt)


    
    try:
        response = model.invoke(prompt)
    except Exception as e:
        print("Error invoking chain:", e)
    return {"response_text":response, "sources":context_obj["sources"]}