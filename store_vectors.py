from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from chunking import chunks

# Load the embedding model on CPU
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu"
)

# Generate embeddings for all chunks
texts = [chunk["text"] for chunk in chunks]
embeddings = model.encode(
    texts,
    convert_to_numpy=True,
    show_progress_bar=True
)

# Create a persistent ChromaDB database beside this script
DB_PATH = Path(__file__).parent / "data" / "chroma_db"
DB_PATH.mkdir(parents=True, exist_ok=True)
client = chromadb.PersistentClient(path=str(DB_PATH))

# Create or access the collection
collection = client.get_or_create_collection(
    name="hospital_documents",
    metadata={"hnsw:space": "cosine"}
)

# Upsert chunks so rerunning this script updates the same IDs
ids = [f"chunk_{index}" for index in range(len(chunks))]
metadatas = [
    {"filename": chunk["filename"], "chunk_index": index}
    for index, chunk in enumerate(chunks)
]
collection.upsert(
    ids=ids,
    documents=texts,
    embeddings=embeddings.tolist(),
    metadatas=metadatas
)

print("Documents stored successfully!")
print("Total chunks stored:", collection.count())
print("Database location:", DB_PATH.resolve())
