from langchain_unstructured import UnstructuredLoader
import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# List of paths are given as parameters. If succeeds, it returns the documents for all pages and pdfs. If not, it returns 0
def unstructured_load_pdf(file_paths):
    try:
        loader = UnstructuredLoader(file_paths)
        docs = loader.load()
        
        if not docs:
            print("Error: No documents loaded.")
            return 0

        return docs
    except Exception as e:
        print(f"Error loading documents: {e}")
        return 0


# Given page numbers, this function prints out the content of corresponding pages.
def unstructured_print_page_content(docs, page_numbers):
    if docs is None:
        print("Error: 'docs' is None. Ensure documents are loaded correctly.")
        return

    for i in page_numbers:
        corresponding_page_docs = [doc for doc in docs if doc.metadata.get("page_number") == i]

        print(f"Page {corresponding_page_docs[0].metadata.get("page_number")}:")
        for doc in corresponding_page_docs:
            print(doc.page_content)


# Given page numbers, this function returns the documents for corresponding pages.
def unstructured_return_specific_pages(docs, page_numbers):
    res = []
    for i in page_numbers:
        corresponding_page_docs = [doc for doc in docs if doc.metadata.get("page_number") == i]

        for doc in corresponding_page_docs:
            res.append(doc)

    return res
    

# Does not work right now, if we are going to need it. We can fix it.
def retrieve_specific_section(docs, sectionName):
    section_docs = []
    parent_id = -1
    for doc in docs:
        if doc.metadata["category"] == "Title" and sectionName in doc.page_content:
            parent_id = doc.metadata["element_id"]

        if doc.metadata.get("parent_id") == parent_id:
            section_docs.append(doc)

    for doc in section_docs:
        print(doc.section_docs)

    return section_docs