"""Creative (banner) endpoints: create-image + multipart upload, moderation status."""
from pathlib import Path

from .client import Client


def available_sizes(c: Client, creative_type: str = "image"):
    return c.get("/api/creatives/available-sizes", type=creative_type)


def create_image(c: Client, group_id: str, title: str, click_url: str,
                 run_after_approval: bool = True, creative_id: str | None = None) -> str:
    body = {
        "groupId": group_id,
        "title": title,
        "clickUrl": click_url,
        "isRunAdAfterApproval": run_after_approval,
    }
    if creative_id:
        body["creativeId"] = creative_id
    return c.post("/api/creatives/create-image", body)


def upload_images(c: Client, creative_id: str, image_paths: list[str | Path],
                  images_for_remove: list[str] | None = None):
    # NB: sending an empty imagesForRemove makes the endpoint 500 — omit unless removing
    data = {"creativeId": creative_id}
    if images_for_remove:
        for url in images_for_remove:
            data.setdefault("imagesForRemove[]", []).append(url)
    files = [("images", (Path(p).name, open(p, "rb"), "image/png")) for p in image_paths]
    try:
        return c.post("/api/creatives/upload-images", data=data, files=files)
    finally:
        for _, (_, fh, _) in files:
            fh.close()


def create_text(c: Client, group_id: str, title: str, click_url: str,
                description1: str, description2: str, display_url: str,
                run_after_approval: bool = True, creative_id: str | None = None) -> str:
    body = {
        "groupId": group_id,
        "title": title,
        "clickUrl": click_url,
        "description1": description1,
        "description2": description2,
        "displayUrl": display_url,
        "isRunAdAfterApproval": run_after_approval,
    }
    if creative_id:
        body["creativeId"] = creative_id
    return c.post("/api/creatives/create-text", body)


def list_(c: Client, by: str = "user", entity_id: str | None = None,
          skip: int = 0, limit: int = 100, archived: int = 0):
    return c.get("/api/creatives/list", by=by, id=entity_id, skip=skip,
                 limit=limit, archived=archived)


def info(c: Client, creative_id: str):
    return c.get("/api/creatives/creative-info", id=creative_id)


def activate(c: Client, creative_id: str, is_active: bool):
    return c.post("/api/creatives/activate-creative", {"id": creative_id, "isActive": is_active})
