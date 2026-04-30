"""Public parsing entry points."""


def parse_document(path: str) -> None:
    """Parse a technical document.

    Args:
        path: Path to the document to parse.

    Raises:
        NotImplementedError: PDF parsing is not implemented yet.
    """
    raise NotImplementedError(
        f"PDF parsing is not implemented yet for document path: {path}"
    )
