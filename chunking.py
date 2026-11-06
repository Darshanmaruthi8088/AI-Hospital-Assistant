from ingest import documents

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
chunks = []

for document in documents:
    text = document["content"]
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        chunks.append({
            "filename": document["filename"],
            "text": chunk_text
        })
        start += CHUNK_SIZE - CHUNK_OVERLAP

# Display chunks when this script is run directly
if __name__ == "__main__":
    print("Total documents:", len(documents))
    print("Total chunks:", len(chunks))
    for i, chunk in enumerate(chunks):
        print("\n" + "=" * 50)
        print("Chunk:", i + 1)
        print("Source:", chunk["filename"])
        print("Text:", chunk["text"])
