from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# Load the embedding model on CPU
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu"
)

# Connect to the existing persistent database
DB_PATH = Path(__file__).parent / "data" / "chroma_db"
client = chromadb.PersistentClient(path=str(DB_PATH))
collection = client.get_collection(name="hospital_documents")

# Ask a question
query = "What are the laboratory working hours?"

# Convert the question into an embedding
query_embedding = model.encode(query, convert_to_numpy=True).tolist()

# Search for the 3 most relevant chunks
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

# Display retrieved results
print("\nUser Question:", query)
print("\nRetrieved Documents:")
for i, text in enumerate(results["documents"][0]):
    metadata = results["metadatas"][0][i]
    distance = results["distances"][0][i]
    print("\n" + "=" * 50)
    print("Result:", i + 1)
    print("Source:", metadata["filename"])
    print("Cosine distance:", f"{distance:.4f}")
    print("Text:")
    print(text)
