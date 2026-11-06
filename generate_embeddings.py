from chunking import chunks
from sentence_transformers import SentenceTransformer

# Load the embedding model on CPU
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu"
)

# Extract chunk text
texts = [chunk["text"] for chunk in chunks]

# Generate embeddings
embeddings = model.encode(
    texts,
    convert_to_numpy=True,
    show_progress_bar=True
)

# Display results
print("\nTotal chunks:", len(texts))
print("Embedding dimensions:", model.get_embedding_dimension())
print("Embedding shape:", embeddings.shape)
print("\nFirst chunk:")
print(texts[0])
print("\nFirst embedding (first 10 values):")
print(embeddings[0][:10])
