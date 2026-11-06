from pathlib import Path
import json
import urllib.request

import chromadb
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OLLAMA_MODEL_NAME = "llama3.2:3b"
OLLAMA_URL = "http://localhost:11434/api/generate"
DISTANCE_THRESHOLD = 0.5
N_RESULTS = 3
DB_PATH = Path(__file__).parent / "data" / "chroma_db"
UNSUPPORTED_ANSWER = "The provided documents do not contain the requested information."

_model = None
_collection = None


def _get_resources():
    """Load the embedding model and connect to the persistent collection once."""
    global _model, _collection

    if _model is None:
        print("Loading embedding model...")
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME, device="cpu")

    if _collection is None:
        client = chromadb.PersistentClient(path=str(DB_PATH))
        _collection = client.get_collection(name="hospital_documents")

    return _model, _collection


def answer_question(question: str) -> dict:
    """Answer a question from retrieved hospital documents and return its sources."""
    query = question.strip()
    if not query:
        raise ValueError("Please enter a question.")

    model, collection = _get_resources()
    if collection.count() == 0:
        return {"answer": UNSUPPORTED_ANSWER, "sources": []}

    query_embedding = model.encode(query, convert_to_numpy=True).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(N_RESULTS, collection.count()),
    )

    distances = results["distances"][0]
    relevant_indices = [
        index
        for index, distance in enumerate(distances)
        if distance <= DISTANCE_THRESHOLD
    ]
    if not relevant_indices:
        return {"answer": UNSUPPORTED_ANSWER, "sources": []}

    context_parts = []
    sources_by_filename = {}
    for index in relevant_indices:
        text = results["documents"][0][index]
        metadata = results["metadatas"][0][index] or {}
        filename = metadata.get("filename", "unknown")
        distance = float(distances[index])
        context_parts.append(f"Source: {filename}\nContent: {text}")

        previous = sources_by_filename.get(filename)
        if previous is None or distance < previous["distance"]:
            sources_by_filename[filename] = {
                "filename": filename,
                "distance": distance,
            }

    context = "\n\n".join(context_parts)
    prompt = f"""You are an AI Hospital Information Assistant.
Answer the user's question using only the information in the context.

Rules:
1. Never invent hospital policies or information.
2. If the answer is unavailable in the context, say so clearly.
3. Keep the answer simple and concise.
4. Add inline citations in the exact format [Source: filename] after factual statements.
5. Use only filenames shown in the context.
6. Cite only documents that support the statement.

Context:
{context}

User Question:
{query}

Answer:"""

    payload = {
        "model": OLLAMA_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))

    return {
        "answer": result["response"].strip(),
        "sources": list(sources_by_filename.values()),
    }


if __name__ == "__main__":
    question = input("\nEnter your question: ")
    try:
        result = answer_question(question)
    except Exception as error:
        raise SystemExit(f"Error generating answer: {error}") from error

    print("\nAnswer:")
    print(result["answer"])
    print("\nSources:")
    for source in result["sources"]:
        print(
            f"- {source['filename']} "
            f"(Distance: {source['distance']:.4f})"
        )
