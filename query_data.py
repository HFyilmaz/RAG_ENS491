import argparse
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM

from get_embedding_function import get_embedding_function

CHROMA_PATH = "chroma"

PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---
{instruction}
Answer the question based on the above context: {question}
"""

# closer to 0 -> more relevant yet lesser results
SIMILARITY_THRESHOLD = 0.75

#closest k chunks that returned from database similarity search
CLOSEST_K_CHUNK = 10

# Additional instructions for LLM modal
ADDITIONAL_INSTRUCTION =  "" # "if there exist, indicate section number when you are answering from the context"

def main():
    # Create CLI.
    parser = argparse.ArgumentParser()
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    query_text = args.query_text
    query_rag(query_text)


def query_rag(query_text: str):
    # Prepare the DB.
    embedding_function = get_embedding_function()
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embedding_function)

    # Search the DB.
    results = db.similarity_search_with_score(query_text, k=CLOSEST_K_CHUNK)

    filtered_results = [
        (doc, score) for doc, score in results if score <= SIMILARITY_THRESHOLD
    ]

    if filtered_results:
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in filtered_results])
    else:
        context_text = "There is nothing found in the application. Say user that you didn't find anything. Do not try to guess answer"

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text,instruction= ADDITIONAL_INSTRUCTION)
    # print(prompt)

    model = OllamaLLM(model="llama3.1")
    response_text = model.invoke(prompt)

    sources = [doc.metadata.get("id", None) for doc, _score in filtered_results]
    formatted_response = f"Response: {response_text}\nSources: {sources}"
    print(formatted_response)

    #FOR TESTING:
    print("\nDEBUG: ALL THE 10 closest result:")
    print([(doc.metadata.get("id", None), _score) for doc, _score in results])
    return response_text


if __name__ == "__main__":
    main()