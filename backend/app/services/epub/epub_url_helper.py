"""
URL Helper utilities for EPUB processing
Centralizes URL encoding, decoding, and path normalization
"""

import urllib.parse


class EPUBURLHelper:
    """Centralized URL handling for EPUB files and paths"""

    @staticmethod
    def normalize_image_path(image_path: str) -> str:
        """
        Normalize image paths to be safe and consistent

        Args:
            image_path: Raw image path from EPUB content

        Returns:
            Normalized path safe for URL construction
        """
        if not image_path:
            return ""

        # Remove leading/trailing whitespace
        path = image_path.strip()

        # Handle empty paths
        if not path:
            return ""

        # Skip already absolute URLs
        if path.startswith(("http://", "https://", "data:", "blob:")):
            return path

        # Remove leading ./ and ../
        path = path.lstrip("./")

        # Handle relative paths with ../
        while path.startswith("../"):
            path = path[3:]

        # Handle Windows-style paths
        while path.startswith("..\\"):
            path = path[3:]

        # Remove any remaining leading slashes to avoid double slashes
        path = path.lstrip("/\\")

        # Basic security: prevent path traversal
        if ".." in path or path.startswith("/") or "\\" in path:
            # Replace problematic characters
            path = path.replace("..", "").replace("\\", "/")

        return path

    @staticmethod
    def encode_filename_for_url(filename: str) -> str:
        """
        Safely encode filename for use in URLs

        Args:
            filename: Raw filename

        Returns:
            URL-encoded filename
        """
        if not filename:
            return ""

        # Use urllib.parse.quote to handle special characters
        # safe='' means encode everything except alphanumeric and '_.-'
        return urllib.parse.quote(filename, safe="")

    @staticmethod
    def decode_filename_from_url(encoded_filename: str) -> str:
        """
        Safely decode filename from URL

        Args:
            encoded_filename: URL-encoded filename

        Returns:
            Decoded filename
        """
        if not encoded_filename:
            return ""

        try:
            return urllib.parse.unquote(encoded_filename)
        except Exception:
            # If decoding fails, return as-is
            return encoded_filename

    @staticmethod
    def build_image_url(base_url: str, filename: str, image_path: str) -> str:
        """
        Build a complete image URL with proper encoding

        Args:
            base_url: Base URL (e.g., "http://localhost:8000")
            filename: EPUB filename
            image_path: Normalized image path

        Returns:
            Complete encoded URL
        """
        if not all([base_url, filename, image_path]):
            return ""

        # Normalize the image path
        normalized_path = EPUBURLHelper.normalize_image_path(image_path)

        if not normalized_path:
            return ""

        # Encode components separately
        encoded_filename = EPUBURLHelper.encode_filename_for_url(filename)
        encoded_image_path = urllib.parse.quote(normalized_path, safe="/")

        # Build URL with proper path joining
        return (
            f"{base_url.rstrip('/')}/epub/{encoded_filename}/image/{encoded_image_path}"
        )

    @staticmethod
    def extract_image_path_from_epub_item(item_name: str) -> str:
        """
        Extract clean image path from EPUB item name

        Args:
            item_name: Raw item name from EPUB

        Returns:
            Clean image path
        """
        if not item_name:
            return ""

        # Basic normalization
        path = item_name.strip()

        # Remove leading path separators that might cause issues
        path = path.lstrip("/\\")

        return path

    @staticmethod
    def is_valid_image_path(image_path: str) -> bool:
        """
        Validate that an image path is safe to use

        Args:
            image_path: Image path to validate

        Returns:
            True if path is safe, False otherwise
        """
        if not image_path or not isinstance(image_path, str):
            return False

        # Check for path traversal attempts
        if ".." in image_path:
            return False

        # Check for absolute paths (security risk)
        if image_path.startswith(("/", "\\")):
            return False

        # Check for null bytes or other dangerous characters
        dangerous_chars = ["\x00", "\n", "\r", "\t"]
        if any(char in image_path for char in dangerous_chars):
            return False

        return True
