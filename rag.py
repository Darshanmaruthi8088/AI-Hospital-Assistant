from pathlib import Path
import json
import urllib.request

import chromadb
from sentence_transformers import SentenceTransformer

# 1. Load the embedding model on CPU
print("Loading embedding model...")
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu"
)

# 2. Connect to the existing ChromaDB
DB_PATH = Path(__file__).parent / "data" / "chroma_db"
client = chromadb.PersistentClient(path=str(DB_PATH))
collection = client.get_collection(name="hospital_documents")

# 3. Get the user's question
query = input("\nEnter your hospital-related question: ").strip()

if not query:
    raise SystemExit("Please enter a question.")

# 4. Convert the question into an embedding
query_embedding = model.encode(query, convert_to_numpy=True).tolist()

# 5. Retrieve the 3 most relevant document chunks
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3
)

# 6. Filter retrieved chunks using cosine distance
DISTANCE_THRESHOLD = 0.5
relevant_indices = [
    i
    for i, distance in enumerate(results["distances"][0])
    if distance <= DISTANCE_THRESHOLD
]

# Stop if no relevant documents are found
if not relevant_indices:
    print("\nAnswer:")
    print("The provided documents do not contain the requested information.")
    raise SystemExit

# 7. Prepare context using only relevant chunks
context_parts = []
for i in relevant_indices:
    text = results["documents"][0][i]
    metadata = results["metadatas"][0][i]
    source = metadata["filename"]
    context_parts.append(f"Source: {source}\nContent: {text}")
context = "\n\n".join(context_parts)

# 8. Prepare a grounded prompt for the LLM
prompt = f"""You are an AI Hospital Information Assistant.
Answer the user's question using ONLY the information provided in the context.

Rules:
1. Never invent hospital policies or information.
2. If the answer is unavailable, clearly say so.
3. Keep the answer simple and concise.
4. After every factual statement, include an inline citation using this exact format: [Source: filename].
5. Use only filenames provided in the context.
6. Cite only documents that actually support the statement.

Context:
{context}

User Question:
{query}

Answer:"""

# 9. Send the prompt to Ollama's local API
payload = {
    "model": "llama3.2:3b",
    "prompt": prompt,
    "stream": False
}
request = urllib.request.Request(
    "http://localhost:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("\nAnswer:")
    print(result["response"].strip())
    print("\nRetrieved Sources:")
    for i in relevant_indices:
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        print(
            f"- {metadata['filename']} "
            f"(Distance: {distance:.4f})"
        )
except Exception as error:
    print("Error connecting to Ollama:", error)
