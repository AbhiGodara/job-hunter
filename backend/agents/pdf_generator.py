"""
PDF Generator — converts Markdown to professionally styled PDF via Playwright.
Ported from generate_pdf.mjs concepts.

Uses Playwright's Chromium headless to render styled HTML and produce
clean, ATS-parseable PDFs for tailored resumes and interview prep guides.
"""
import os
import re
import logging
import asyncio
from typing import Optional

log = logging.getLogger(__name__)

PDF_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../../data/pdfs")


def normalize_text_for_ats(text: str) -> str:
    """
    Normalize text for ATS compatibility by converting problematic Unicode.
    ATS parsers often fail on em-dashes, smart quotes, zero-width characters.
    Ported from generate_pdf.mjs normalizeTextForATS().
    """
    # Em-dash → hyphen
    text = text.replace("\u2014", "-")
    # En-dash → hyphen
    text = text.replace("\u2013", "-")
    # Smart double quotes → regular quotes
    text = re.sub(r"[\u201C\u201D\u201E\u201F]", '"', text)
    # Smart single quotes → apostrophe
    text = re.sub(r"[\u2018\u2019\u201A\u201B]", "'", text)
    # Ellipsis → three dots
    text = text.replace("\u2026", "...")
    # Zero-width characters → remove
    text = re.sub(r"[\u200B\u200C\u200D\u2060\uFEFF]", "", text)
    # Non-breaking space → regular space
    text = text.replace("\u00A0", " ")
    return text


def markdown_to_html(markdown_text: str, title: str = "Document") -> str:
    """Convert Markdown text to styled HTML suitable for PDF rendering."""
    try:
        import markdown
        body = markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    except ImportError:
        # Fallback: basic markdown conversion
        body = _basic_markdown(markdown_text)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        body {{
            font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #1a1a1a;
            max-width: 100%;
            padding: 0;
            margin: 0;
        }}
        
        h1 {{
            font-size: 18pt;
            font-weight: 700;
            color: #111;
            border-bottom: 2px solid #333;
            padding-bottom: 4pt;
            margin-top: 0;
            margin-bottom: 8pt;
        }}
        
        h2 {{
            font-size: 13pt;
            font-weight: 600;
            color: #222;
            border-bottom: 1px solid #ccc;
            padding-bottom: 3pt;
            margin-top: 14pt;
            margin-bottom: 6pt;
        }}
        
        h3 {{
            font-size: 11pt;
            font-weight: 600;
            color: #333;
            margin-top: 10pt;
            margin-bottom: 4pt;
        }}
        
        p {{
            margin-bottom: 6pt;
        }}
        
        ul, ol {{
            margin-bottom: 6pt;
            padding-left: 18pt;
        }}
        
        li {{
            margin-bottom: 2pt;
        }}
        
        strong {{
            font-weight: 600;
        }}
        
        code {{
            background: #f4f4f4;
            padding: 1pt 4pt;
            border-radius: 3pt;
            font-size: 10pt;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 10pt;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 6pt 8pt;
            text-align: left;
            font-size: 10pt;
        }}
        
        th {{
            background: #f0f0f0;
            font-weight: 600;
        }}
        
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 10pt 0;
        }}
    </style>
</head>
<body>
{body}
</body>
</html>"""
    return html


def _basic_markdown(text: str) -> str:
    """Minimal Markdown → HTML fallback if python-markdown is not installed."""
    lines = text.split("\n")
    html_parts = []
    for line in lines:
        if line.startswith("### "):
            html_parts.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_parts.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_parts.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- "):
            html_parts.append(f"<li>{line[2:]}</li>")
        elif line.startswith("**") and line.endswith("**"):
            html_parts.append(f"<p><strong>{line[2:-2]}</strong></p>")
        elif line.strip() == "":
            html_parts.append("<br>")
        else:
            # Bold text inline
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html_parts.append(f"<p>{line}</p>")
    return "\n".join(html_parts)


async def _generate_pdf_async(html_content: str, output_path: str) -> dict:
    """Use Playwright Chromium to render HTML and generate PDF."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content(html_content, wait_until="networkidle")

            # Wait for fonts to load
            try:
                await page.evaluate("() => document.fonts.ready")
            except Exception:
                pass

            pdf_buffer = await page.pdf(
                format="A4",
                print_background=True,
                margin={
                    "top": "0.6in",
                    "right": "0.6in",
                    "bottom": "0.6in",
                    "left": "0.6in",
                },
            )

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(pdf_buffer)

            size_kb = len(pdf_buffer) / 1024
            log.info(f"PDF generated: {output_path} ({size_kb:.1f} KB)")
            return {"path": output_path, "size_kb": round(size_kb, 1)}

        finally:
            await browser.close()


def generate_pdf(markdown_text: str, filename: str, title: str = "Document") -> Optional[str]:
    """
    Convert Markdown text to a professionally styled PDF file.
    
    Args:
        markdown_text: Raw markdown content
        filename: Output filename (e.g. 'tailored_resume_123.pdf')
        title: Document title for the HTML header
        
    Returns:
        Absolute path to the generated PDF, or None on failure.
    """
    try:
        # Normalize text for ATS compatibility
        clean_text = normalize_text_for_ats(markdown_text)

        # Convert to styled HTML
        html = markdown_to_html(clean_text, title=title)

        # Generate PDF
        os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(PDF_OUTPUT_DIR, filename)

        asyncio.run(_generate_pdf_async(html, output_path))
        return output_path

    except Exception as e:
        log.error(f"PDF generation failed for {filename}: {e}")
        return None
