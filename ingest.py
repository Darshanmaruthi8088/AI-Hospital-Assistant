from pathlib import Path

# Folder containing hospital documents
DATA_FOLDER = Path(__file__).parent / "data" / "raw"
documents = []

# Read all text files
for file_path in DATA_FOLDER.glob("*.txt"):
    with open(file_path, "r", encoding="utf-8-sig") as file:
        content = file.read()
    documents.append({
        "filename": file_path.name,
        "content": content
    })

# Display extracted documents when this script is run directly
if __name__ == "__main__":
    print("Total documents loaded:", len(documents))
    for document in documents:
        print("\n" + "=" * 50)
        print("Filename:", document["filename"])
        print("Content:")
        print(document["content"])
