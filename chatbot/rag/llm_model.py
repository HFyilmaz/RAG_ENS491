from .vectordb import get_embedding_function, get_embedding_function_ollama
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langchain_chroma import Chroma

from django.conf import settings
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# TODO: Needs to be set in the admin panel
# closer to 0 -> more relevant yet lesser results
SIMILARITY_THRESHOLD = 0.8

# TODO: Needs to be set in the admin panel
CLOSEST_K_CHUNK = 5

model_kwargs = {
    "max_length": 128
}

# To run on cloud with Hugging Face (key in .env file is required)
'''
hf_key = os.getenv("HuggingFace_KEY")
repo_id = "mistralai/Mixtral-8x7B-Instruct-v0.1"
llm = HuggingFaceEndpoint(
    repo_id=repo_id,
    temperature=0.5,
    model_kwargs=model_kwargs,
    huggingfacehub_api_token=hf_key,
)
'''

# To run on local machine with Ollama (ollama needs to be installed)
from langchain_ollama import OllamaLLM
llm_ollama = OllamaLLM(model="llama3.1")

def query_llm(query_text: str):
    try:
        # Initialize embedding function and database
        embedding_function = get_embedding_function_ollama()

        db = Chroma(
            persist_directory=settings.CHROMA_PATH,
            embedding_function=embedding_function
        )

        PROMPT_TEMPLATE = """
        Answer the question based only on the following context:
        {context}

        ---
        Answer the question based on the above context: {question}
        """

        # Search the DB
        results = db.similarity_search_with_score(query_text, k=CLOSEST_K_CHUNK)

        # Filter results
        filtered_results = [
            (doc, score) for doc, score in results if score <= SIMILARITY_THRESHOLD
        ]

        if filtered_results:
            context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in filtered_results])
        else:
            context_text = "There is nothing found in the application. Say user that you didn't find anything. Do not try to guess answer"

        # Format the prompt
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text)

        # Send the prompt to the model
        response_text = llm_ollama.invoke(prompt)

        # Extract sources
        sources = [doc.metadata.get("id", None) for doc, _score in filtered_results]

        # Format the response in JSON format
        formatted_response = {
            "response": response_text.strip(),
            "sources": sources
        }

        return formatted_response

    except Exception as e:
        return {"error": f"An error occurred while processing the request: {e}"}
