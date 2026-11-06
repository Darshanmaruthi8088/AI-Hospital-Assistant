import chromadb

client = chromadb.Client()
collection = client.create_collection(name="hospital_test")

print("ChromaDB client created successfully")
print("Collection created:", collection.name)
