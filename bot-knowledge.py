from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.vectorstores import FAISS

from langchain_community.embeddings import (
    HuggingFaceEmbeddings
)

with open(
    "botinfo.txt",
    "r",
    encoding="utf-8"
) as f:

    text = f.read()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50
)

chunks = splitter.split_text(text)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

db = FAISS.from_texts(
    chunks,
    embeddings
)

db.save_local(
    "bot_knowledge_db"
)

print("Knowledge Base Created")