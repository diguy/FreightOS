import requests

def main() -> None:
    print("app: backend-lab")
    print("version: 0.1.0")

    response = requests.get(
        "https://httpbin.org/get",
        timeout=5,
    )
    response.raise_for_status()

    print("status:", response.status_code)
    print("url:", response.json()["url"])