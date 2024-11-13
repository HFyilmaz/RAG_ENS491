import asyncio
from simple_loader import load_data_simple
from loader import unstructured_load_pdf, unstructured_print_page_content, unstructured_return_specific_pages

file_paths = [
    "./data/R000r5e.pdf",
]

def document_loading():
    docs = unstructured_load_pdf(file_paths)
    if(docs == 0):
        return 0
    
    # unstructured_print_page_content(docs, range(12, 14))

    # specific_docs = unstructured_return_specific_pages(docs, range(12, 14))
    # print(specific_docs[0].metadata)
    # print(specific_docs[0].page_content)


async def main():
    document_loading()


if __name__ == "__main__":
    asyncio.run(main())
