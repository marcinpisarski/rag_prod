#!/usr/bin/env python3
"""Upload all sample documents from eval/sample and wait until indexed."""

import argparse
import mimetypes
import time
from pathlib import Path

import requests

SAMPLE_DIR = Path(__file__).parent / "sample"
SUPPORTED_EXTENSIONS = {".txt", ".md"}
SKIP_FILES = {"SETUP.md"}


def discover_sample_files() -> list[Path]:
    """Return evaluable files from eval/sample (README, LICENSE, etc.)."""
    files = sorted(
        path
        for path in SAMPLE_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and path.name not in SKIP_FILES
    )
    if not files:
        raise FileNotFoundError(
            f"No sample files found in {SAMPLE_DIR}. "
            f"Expected .txt or .md files (except {', '.join(SKIP_FILES)})."
        )
    return files


def mime_type_for(path: Path) -> str:
    if path.suffix.lower() == ".md":
        return "text/markdown"
    return mimetypes.guess_type(path.name)[0] or "text/plain"


def wait_for_document(api_url: str, document_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = requests.get(f"{api_url}/api/documents/{document_id}/status", timeout=10)
        response.raise_for_status()
        status = response.json()
        if status.get("status") == "ready":
            return status
        if status.get("status") == "failed":
            raise RuntimeError(f"Document {document_id} processing failed")
        time.sleep(2)
    raise TimeoutError(f"Document {document_id} not ready after {timeout}s")


def upload_file(api_url: str, file_path: Path) -> dict:
    with open(file_path, "rb") as handle:
        response = requests.post(
            f"{api_url}/api/documents/upload",
            files={"file": (file_path.name, handle, mime_type_for(file_path))},
            data={"title": file_path.stem},
            timeout=60,
        )
    response.raise_for_status()
    return response.json()


def load_sample_docs(api_url: str = "http://localhost:8000", timeout: int = 180):
    sample_files = discover_sample_files()
    print(f"Loading {len(sample_files)} documents from {SAMPLE_DIR}")
    print(f"Target API: {api_url}")

    health = requests.get(f"{api_url}/health", timeout=10)
    health.raise_for_status()
    print("API is healthy")

    uploaded = []
    for file_path in sample_files:
        print(f"\nUploading {file_path.name}...")
        result = upload_file(api_url, file_path)
        document_id = result["document_id"]
        print(f"  queued: {document_id}")

        status = wait_for_document(api_url, document_id, timeout=timeout)
        print(f"  ready: {status.get('segment_count', 0)} segments")
        uploaded.append(status)

    print("\nAll sample documents indexed:")
    for item in uploaded:
        print(
            f"  - {item.get('title')}: {item.get('segment_count', 0)} segments "
            f"({item.get('document_id')})"
        )
    return uploaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload eval/sample documents (*.md, *.txt) into the API"
    )
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    load_sample_docs(api_url=args.api_url, timeout=args.timeout)
