import requests
import json
import os

OLLAMA_URL = "http://localhost:11434/api/generate"

def ask_ai(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": "phi",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

MEMORY_FILE = "memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def format_memory(memory):
    return "\n".join(
        [f"{m['original']} -> {m['category']}" for m in memory[-10:]]
    )

def analyze_file(filename, content=""):
    memory = load_memory()
    history = format_memory(memory)

    prompt = f"""
    You are an intelligent file organization agent.

    Your job is to organize files consistently and logically.

    Previous decisions:
    {history}

    Now analyze this file:

    Filename: {filename}
    Content: {content}

    Think step-by-step:
    1. What type of file is this?
    2. What is its purpose?
    3. What would be a consistent category based on past decisions?

    Then decide:

    Category: <category>
    Filename: <clean filename>

    Return ONLY:
    Category: ...
    Filename: ...
    """

    result = ask_ai(prompt)

    name = "unknown"
    category = "Other"

    for line in result.split("\n"):
        line = line.strip().lower()

        if line.startswith("filename:"):
            candidate_name = line.split("filename:", 1)[1].strip()
            if candidate_name:
                name = candidate_name

        if line.startswith("category:"):
            category = line.split("category:")[1].strip()
    
    memory.append({
    "original": filename,
    "category": category,
    "new_name": name
    })

    save_memory(memory)

    return name, category