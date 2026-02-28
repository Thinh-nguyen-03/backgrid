"""Content fetching and text extraction from URLs, PDFs, and raw text."""

import logging

logger = logging.getLogger(__name__)


class ContentFetcher:
    """Fetches and extracts text from various sources."""

    MAX_CONTENT_LENGTH = 50000

    def fetch_url(self, url: str) -> str:
        """Fetch and extract text from a URL."""
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(
            url, timeout=15, headers={"User-Agent": "Backgrid/2.0"}
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[: self.MAX_CONTENT_LENGTH]

    def extract_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        from PyPDF2 import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages[:20]:
            pages.append(page.extract_text() or "")
        text = "\n".join(pages)
        return text[: self.MAX_CONTENT_LENGTH]

    def process_text(self, text: str) -> str:
        """Trim raw text input to max length."""
        return text[: self.MAX_CONTENT_LENGTH]
