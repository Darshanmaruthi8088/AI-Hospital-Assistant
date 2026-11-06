import json
import urllib.request

url = "http://localhost:11434/api/generate"

data = {
    "model": "llama3.2:3b",
    "prompt": "Explain what a hospital laboratory does in 3 simple sentences.",
    "stream": False
}

request = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("Ollama Response:")
    print(result["response"])

except Exception as e:
    print("Error connecting to Ollama:", e)
