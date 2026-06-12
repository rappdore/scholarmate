"""
Shared service singletons.

PDFService and EPUBService each build an in-memory metadata cache (scanning
the books directories and generating thumbnails) on construction. Creating
one instance per router meant several independent caches that drifted apart:
POST /pdf/refresh-cache only refreshed the copy owned by the PDF router, and
deletions evicted entries from one cache while the others kept serving stale
data.

This module owns the single shared instance of each service, mirroring the
``db_service`` singleton in database_service.py. All routers and services
must import these instances instead of constructing their own.
"""

from .epub_service import EPUBService
from .pdf_service import PDFService

pdf_service = PDFService()
epub_service = EPUBService()
