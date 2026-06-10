"""External file processor — submits files to external API for processing, polls for result"""
import logging
from typing import Optional

import httpx

from app.algorithm.model_resolver import model_resolver

logger = logging.getLogger(__name__)


class ExternalFileProcessor:
    """External file processor using model provider configuration.

    Resolves fileProcessorId → model provider config (api_host, api_key).
    Uploads file to {api_host}/upload, polls {api_host}/status/{task_id}.
    """

    def __init__(self, processor_id: str):
        self.processor_id = processor_id
        self._config = None

    def _load_config(self) -> Optional[dict]:
        """Load provider config from the model_providers table"""
        if self._config is not None:
            return self._config

        from app.database import get_db

        db = get_db()
        try:
            row = db.execute(
                "SELECT api_host, api_key_encrypted, api_model FROM model_providers WHERE provider_id=? AND is_enabled=1",
                (self.processor_id,),
            ).fetchone()
            if not row:
                logger.warning(
                    "No enabled provider found for processor_id=%s",
                    self.processor_id,
                )
                return None
            from app.algorithm.crypto import decrypt_key

            self._config = {
                "api_host": row["api_host"].rstrip("/"),
                "api_key": decrypt_key(row["api_key_encrypted"]) if row["api_key_encrypted"] else "",
                "model": row["api_model"] or "",
            }
            return self._config
        finally:
            db.close()

    async def process(self, file_path: str, file_name: str) -> dict:
        """For external processors, process acts as submit + poll with timeout.
        Used when we want synchronous behavior."""
        task_id = await self.submit(file_path)
        # Poll up to 5 minutes (30 * 10s)
        for _ in range(30):
            result = await self.poll(task_id)
            if result is not None:
                return result
            import asyncio

            await asyncio.sleep(10)
        raise TimeoutError(f"External processing timed out for {file_name}")

    async def submit(self, file_path: str) -> str:
        """Upload file to external API, return task_id"""
        cfg = self._load_config()
        if not cfg:
            raise RuntimeError(f"No provider config for processor {self.processor_id}")

        api_host = cfg["api_host"]
        api_key = cfg["api_key"]

        upload_url = f"{api_host}/api/v1/document/upload"

        import os

        async with httpx.AsyncClient(timeout=60) as client:
            with open(file_path, "rb") as f:
                files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

                resp = await client.post(upload_url, files=files, headers=headers)
                resp.raise_for_status()
                data = resp.json()

        task_id = data.get("task_id") or data.get("data", {}).get("taskId") or str(data.get("id", ""))
        if not task_id:
            raise RuntimeError(f"External API returned no task_id: {resp.text[:200]}")

        logger.info(
            "Submitted file to external processor %s: task_id=%s",
            self.processor_id,
            task_id,
        )
        return task_id

    async def poll(self, task_id: str) -> Optional[dict]:
        """Poll external API for processing result.
        Returns None if still processing, dict {content, title} when done."""
        cfg = self._load_config()
        if not cfg:
            raise RuntimeError(f"No provider config for processor {self.processor_id}")

        api_host = cfg["api_host"]
        api_key = cfg["api_key"]

        status_url = f"{api_host}/api/v1/document/status/{task_id}"

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(status_url, headers=headers)

                if resp.status_code == 404:
                    return None  # Not ready yet
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise

        # Check status field
        status = data.get("status", data.get("data", {}).get("status", "processing"))
        if status in ("processing", "pending", "running", None, ""):
            return None

        if status in ("failed", "error"):
            error = data.get("error", data.get("message", "Unknown error"))
            raise RuntimeError(f"External processing failed: {error}")

        # Extract content
        document = data.get("document", data.get("data", {}).get("document", data))
        content = document.get("content") or document.get("text") or document.get("markdown", "")
        title = document.get("title") or document.get("name", "")

        if not content:
            # Try alternate format: result embedded in data
            content = data.get("content") or data.get("text") or data.get("result", "")

        logger.info(
            "External processor completed: task_id=%s content_len=%d",
            task_id,
            len(content),
        )
        return {"content": content, "title": title}

    def is_async(self) -> bool:
        return True


# Provider ID to processor ID mapping (generic external)
EXTERNAL_PROCESSOR_IDS = {
    "doc2x": "doc2x",
    "mineru": "mineru",
    "mistral-ocr": "mistral-ocr",
    "paddleocr": "paddleocr",
}
