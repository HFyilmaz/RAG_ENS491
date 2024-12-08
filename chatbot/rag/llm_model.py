from .vectordb import get_embedding_function
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma

from django.conf import settings
from dotenv import load_dotenv
import os

load_dotenv()


hf_key = os.getenv("HuggingFace_KEY")
repo_id = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# TODO: Needs to be set in the admin panel
# closer to 0 -> more relevant yet lesser results
SIMILARITY_THRESHOLD = 0.5

# TODO: Needs to be set in the admin panel
CLOSEST_K_CHUNK = 5

model_kwargs = {
    "max_length": 128
}
llm = HuggingFaceEndpoint(
    repo_id=repo_id,
    temperature=0.5,
    model_kwargs=model_kwargs,
    huggingfacehub_api_token=hf_key,
)


def query_llm(query_text: str):
    embedding_function = get_embedding_function()
    db = Chroma(
        persist_directory = settings.CHROMA_PATH,
        embedding_function = embedding_function
    )
    PROMPT_TEMPLATE = """
    Answer the question based only on the following context:
    {context}

    ---
    Answer the question based on the above context: {question}
    """
    # Search the DB.
    results = db.similarity_search_with_score(query_text, k=CLOSEST_K_CHUNK)

    filtered_results = [
        (doc, score) for doc, score in results if score <= SIMILARITY_THRESHOLD
    ]

    if filtered_results:
        context_text = "\n\n---\n\n".join([doc.page_content for doc,_score in filtered_results])
    else:
        context_text = "There is nothing found in the application. Say user that you didn't find anything. Do not try to guess answer"

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt= prompt_template.format(context=context_text, question=query_text)
    # Directing the prompt to the model
    response_text = llm.invoke(prompt)

    sources = [doc.metadata.get("id", None) for doc, _score in results]
    formatted_response_text = f"Response: {response_text}\nSources: {sources}"
    return formatted_response_text