"""
Tests for EPUBContentProcessor HTML sanitization (bug B-15b).

The sanitizer must use a real HTML parser so common regex evasions
(unclosed <script> tags, attributes split across whitespace) cannot bypass
script/event-handler/javascript: stripping, while normal EPUB content and
styling pass through untouched.
"""

import pytest

from app.services.epub.epub_content_processor import EPUBContentProcessor


@pytest.fixture
def processor():
    return EPUBContentProcessor()


def sanitize(processor: EPUBContentProcessor, html: str) -> str:
    return processor._sanitize_html(html)


class TestScriptRemoval:
    def test_script_tag_removed(self, processor):
        result = sanitize(
            processor, "<body><p>safe</p><script>alert('xss')</script></body>"
        )
        assert "<script" not in result.lower()
        assert "alert" not in result
        assert "<p>safe</p>" in result

    def test_unclosed_script_tag_evasion_removed(self, processor):
        # Regex-based stripping that requires </script> misses this.
        result = sanitize(processor, "<body><p>safe</p><script>alert('xss')</body>")
        assert "<script" not in result.lower()
        assert "alert" not in result
        assert "safe" in result

    def test_mixed_case_script_removed(self, processor):
        result = sanitize(
            processor, "<body><ScRiPt>alert('xss')</ScRiPt><p>ok</p></body>"
        )
        assert "script" not in result.lower()
        assert "alert" not in result
        assert "<p>ok</p>" in result

    def test_script_with_attributes_removed(self, processor):
        result = sanitize(
            processor,
            '<body><script type="text/javascript" src="evil.js"></script>'
            "<p>ok</p></body>",
        )
        assert "script" not in result.lower()
        assert "evil.js" not in result


class TestEventHandlerStripping:
    def test_onclick_stripped(self, processor):
        result = sanitize(
            processor, '<body><div onclick="steal()">click me</div></body>'
        )
        assert "onclick" not in result.lower()
        assert "steal" not in result
        assert "click me" in result

    def test_onload_stripped(self, processor):
        result = sanitize(processor, '<body><img src="pic.png" ONLOAD="evil()"></body>')
        assert "onload" not in result.lower()
        assert 'src="pic.png"' in result

    def test_split_attribute_evasion_stripped(self, processor):
        # Whitespace/newlines between the attribute name, '=', and the value
        # defeat naive regexes but not a real parser.
        result = sanitize(
            processor,
            '<body><img src="pic.png" onerror\n   =\n   "alert(1)"></body>',
        )
        assert "onerror" not in result.lower()
        assert "alert" not in result
        assert 'src="pic.png"' in result

    def test_unquoted_handler_stripped(self, processor):
        result = sanitize(processor, "<body><div onmouseover=evil()>hi</div></body>")
        assert "onmouseover" not in result.lower()
        assert "hi" in result


class TestJavascriptUrlNeutralization:
    def test_javascript_href_removed(self, processor):
        result = sanitize(
            processor, '<body><a href="javascript:alert(1)">link</a></body>'
        )
        assert "javascript:" not in result.lower()
        assert "link" in result

    def test_javascript_src_removed(self, processor):
        result = sanitize(processor, '<body><img src="javascript:alert(1)"></body>')
        assert "javascript:" not in result.lower()

    def test_javascript_href_with_whitespace_evasion_removed(self, processor):
        result = sanitize(
            processor, '<body><a href="  java\nscript:alert(1)">link</a></body>'
        )
        assert "script:" not in result.lower()
        assert "link" in result

    def test_mixed_case_javascript_href_removed(self, processor):
        result = sanitize(
            processor, '<body><a href="JaVaScRiPt:alert(1)">link</a></body>'
        )
        assert "alert" not in result
        assert "link" in result

    def test_normal_href_preserved(self, processor):
        result = sanitize(
            processor, '<body><a href="chapter2.xhtml#sec1">next</a></body>'
        )
        assert 'href="chapter2.xhtml#sec1"' in result


class TestNormalContentPreserved:
    def test_styles_and_classes_untouched(self, processor):
        html = (
            "<body>"
            '<div class="chapter" style="color: red; margin: 1em">'
            "<p>Hello <em>world</em></p>"
            "</div>"
            "</body>"
        )
        result = sanitize(processor, html)
        assert 'class="chapter"' in result
        assert 'style="color: red; margin: 1em"' in result
        assert "<em>world</em>" in result

    def test_body_content_extracted_from_full_document(self, processor):
        html = (
            "<!DOCTYPE html>"
            "<html><head><title>Book</title><style>p { color: blue }</style></head>"
            '<body class="epub-body"><p>Chapter text</p></body></html>'
        )
        result = sanitize(processor, html)
        assert "<p>Chapter text</p>" in result
        # body/html/head wrappers must not leak into our container
        assert "<body" not in result.lower()
        assert "<html" not in result.lower()
        assert "<title>" not in result.lower()
        assert "DOCTYPE" not in result

    def test_fragment_without_body_preserved(self, processor):
        html = "<h1>Title</h1><p>Some text</p>"
        result = sanitize(processor, html)
        assert "<h1>Title</h1>" in result
        assert "<p>Some text</p>" in result

    def test_fragment_with_html_wrapper_but_no_body(self, processor):
        html = "<html><head><title>x</title></head><h1>Title</h1></html>"
        result = sanitize(processor, html)
        assert "<h1>Title</h1>" in result
        assert "<html" not in result.lower()
        assert "<title>" not in result.lower()

    def test_empty_input(self, processor):
        assert sanitize(processor, "") == ""
