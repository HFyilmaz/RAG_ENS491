import asyncio
from simple_loader import load_data_simple

file_path = "./data/R000r5e.pdf"
async def main():
    pages = await load_data_simple(file_path)


if __name__ == "__main__":
    asyncio.run(main())
