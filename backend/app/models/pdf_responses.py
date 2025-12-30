from .pdf_metadata import PDFBasicMetadata, PDFExtendedMetadata


class PDFListItem(PDFBasicMetadata):
    """
    PDF item in list view with database IDs.

    Extends basic metadata with database identifiers for API responses.
    Used in GET /api/pdf/list endpoint.
    """

    id: int
    pdf_id: int


class PDFDetailResponse(PDFExtendedMetadata):
    """
    Detailed PDF response with all metadata and database IDs.

    Includes both basic and extended metadata plus database identifiers.
    Used in GET /api/pdf/{pdf_id}/info endpoint.
    """

    id: int
    pdf_id: int
