import json
import os
import httpx
from dotenv import load_dotenv

load_dotenv()


def check_dynatrace(env: str, token: str) -> None:
    url = f"https://{env}/platform-reserved/mcp-gateway/v0.1/servers"
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()


def check_gitlab(token: str) -> None:
    r = httpx.get(
        "https://gitlab.com/api/v4/user",
        headers={"PRIVATE-TOKEN": token},
        timeout=10,
    )
    r.raise_for_status()


def validate(dt_checker=None, gl_checker=None) -> dict:
    if dt_checker is None:
        dt_env = os.environ["DT_ENVIRONMENT"]
        dt_token = os.environ["DT_PLATFORM_TOKEN"]
        dt_checker = lambda: check_dynatrace(dt_env, dt_token)

    if gl_checker is None:
        gl_token = os.environ["GITLAB_TOKEN"]
        gl_checker = lambda: check_gitlab(gl_token)

    results = {}

    try:
        dt_checker()
        results["dynatrace"] = "ok"
    except Exception as e:
        results["dynatrace"] = str(e)

    try:
        gl_checker()
        results["gitlab"] = "ok"
    except Exception as e:
        results["gitlab"] = str(e)

    return results


if __name__ == "__main__":
    print(json.dumps(validate()))
