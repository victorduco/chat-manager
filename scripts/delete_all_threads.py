import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Use environment variable for API URL, fallback to localhost for development
BASE_URL = os.getenv("LANGGRAPH_API_URL", "http://localhost:2024")

HEADERS = {"Content-Type": "application/json"}


def search_threads(limit=100):
    response = requests.post(
        f"{BASE_URL}/threads/search",
        headers=HEADERS,
        json={
            "metadata": {},
            "values": {},
            "limit": limit
        }
    )
    response.raise_for_status()
    return response.json()


def delete_thread(thread_id):
    response = requests.delete(f"{BASE_URL}/threads/{thread_id}")
    if response.status_code in (200, 204):
        print(f"✅ Deleted thread {thread_id}")
    else:
        print(f"⚠️ Failed to delete {thread_id}: {response.status_code}")


def main():
    while True:
        threads = search_threads(limit=100)
        if not threads:
            print("🎉 No more threads to delete.")
            break
        for thread in threads:
            delete_thread(thread["thread_id"])
            time.sleep(0.05)


if __name__ == "__main__":
    main()
