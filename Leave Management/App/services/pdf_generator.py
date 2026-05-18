import logging
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def generate_pdf_from_html(html_content: str) -> bytes:
    """
    Generates a high-fidelity PDF from an HTML string using a headless Chromium browser.
    This preserves modern CSS, flexbox, grid, and web-fonts.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Load the HTML content. We wait for 'networkidle' to ensure 
            # all remote images (like avatars) and fonts are fully downloaded before printing.
            page.set_content(html_content, wait_until="networkidle")
            
            # Wait specifically for all fonts to be ready
            page.evaluate("document.fonts.ready")
            
            # Generate the PDF byte stream
            pdf_bytes = page.pdf(
                format="A4",
                landscape=True,
                print_background=True,  # Crucial for preserving background colors and gradients
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
            )
            
            browser.close()
            return pdf_bytes
            
    except Exception as e:
        logger.error(f"PDF_GENERATOR | Failed to generate PDF: {e}")
        raise
