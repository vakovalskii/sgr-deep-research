"""Utility functions for SGR CLI."""

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: str | Path) -> Optional[str]:
    """Encode image file to base64 data URI.

    Args:
        image_path: Path to image file

    Returns:
        Base64 data URI string or None if error
    """
    try:
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path}")
            return None

        # Determine MIME type from extension
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        ext = image_path.suffix.lower()
        mime_type = mime_types.get(ext, "image/png")

        # Read and encode image
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        return f"data:{mime_type};base64,{image_data}"
    except Exception as e:
        logger.error(f"Error encoding image {image_path}: {e}")
        return None


def is_image_url(url: str) -> bool:
    """Check if string is an image URL.

    Args:
        url: String to check

    Returns:
        True if URL points to an image
    """
    return url.startswith(("http://", "https://")) and any(
        url.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]
    )


def is_base64_image(data: str) -> bool:
    """Check if string is a base64 image data URI.

    Args:
        data: String to check

    Returns:
        True if string is base64 image data URI
    """
    return data.startswith("data:image/") and "base64," in data


def format_image_for_openai(image_path_or_url: str) -> dict:
    """Format image for OpenAI API message format.

    Args:
        image_path_or_url: Image file path, URL, or base64 data URI

    Returns:
        Dictionary with image_url format for OpenAI API
    """
    # If already base64 data URI, use as-is
    if is_base64_image(image_path_or_url):
        return {"type": "image_url", "image_url": {"url": image_path_or_url}}

    # If URL, use as-is
    if is_image_url(image_path_or_url):
        return {"type": "image_url", "image_url": {"url": image_path_or_url}}

    # If file path, encode to base64
    base64_data = encode_image_to_base64(image_path_or_url)
    if base64_data:
        return {"type": "image_url", "image_url": {"url": base64_data}}

    # Fallback: return as text
    logger.warning(f"Could not process image: {image_path_or_url}")
    return {"type": "text", "text": f"[Image: {image_path_or_url}]"}
