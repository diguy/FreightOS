import requests


def main() -> None:
    response = requests.get(
        "https://httpbin.org/get",
        timeout=5,
    )
    response.raise_for_status()

    print("status:", response.status_code)
    print("url:", response.json()["url"])


if __name__ == "__main__":
    main()
