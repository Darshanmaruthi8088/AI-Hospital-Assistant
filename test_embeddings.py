from sentence_transformers import SentenceTransformer

# Load the downloaded embedding model
model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu",
)

# Sample hospital-related information
documents = [
    "The hospital laboratory operates from 8 AM to 5 PM.",
    "Patients must carry their hospital identity card.",
    "Emergency services are available 24 hours a day.",
]

# Convert text into numerical vectors
embeddings = model.encode(documents)

# Display the results
print("Number of documents:", len(documents))
print("Embedding dimensions:", model.get_embedding_dimension())
print("Embedding shape:", embeddings.shape)
print("\nFirst document embedding (first 10 values):")
print(embeddings[0][:10])
