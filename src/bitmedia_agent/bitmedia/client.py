"""Thin Bitmedia API client: X-API-Key auth, {success,data,error} envelope, 429 backoff."""
import os
import time

import httpx

from .. import workspace

BASE_URL = "https://bitmedia.io"


class BitmediaError(RuntimeError):
    pass


class Client:
    def __init__(self, api_key: str | None = None):
        workspace.load_env()
        key = api_key or os.environ.get("BITMEDIA_API_KEY")
        if not key:
            raise BitmediaError("BITMEDIA_API_KEY is not set (workspace .env)")
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"X-API-Key": key},
            timeout=60,
        )

    def request(self, method: str, path: str, *, params=None, json=None,
                data=None, files=None, retries: int = 4):
        for attempt in range(retries + 1):
            resp = self._http.request(method, path, params=params, json=json,
                                      data=data, files=files)
            if resp.status_code == 429 and attempt < retries:
                time.sleep(2 * (2 ** attempt))
                continue
            break
        try:
            body = resp.json()
        except Exception:
            raise BitmediaError(
                f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
        if isinstance(body, dict) and body.get("success") is True:
            return body.get("data")
        err = ""
        if isinstance(body, dict):
            err = body.get("error") or body.get("message") or ""
        raise BitmediaError(f"{method} {path} -> HTTP {resp.status_code}: {err or resp.text[:300]}")

    def get(self, path: str, **params):
        return self.request("GET", path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, json=None, *, data=None, files=None):
        return self.request("POST", path, json=json, data=data, files=files)
