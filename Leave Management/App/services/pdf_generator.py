import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger("lms_service_pdf_generator")

def generate_pdf_from_html(html_content: str) -> bytes:
    """
    Generates a high-fidelity PDF from an HTML string using a headless Chromium browser.
    This preserves modern CSS, flexbox, grid, and web-fonts.
    """
    try:
        logger.info("PDF_GENERATOR | START | Rendering HTML to PDF bytes.")
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
            logger.info("PDF_GENERATOR | SUCCESS | PDF bytes generated.")
            return pdf_bytes
            
    except Exception as e:
        logger.error(f"PDF_GENERATOR | Failed to generate PDF: {e}")
        raise


def _setup_django_for_direct_run():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def _project_root():
    return Path(__file__).resolve().parents[2]


def _generated_pdf_dir():
    output_dir = _project_root() / "generated_pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _safe_file_stem(value):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return stem or "manual_pdf"


def _timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _read_last_weekly_report_info():
    tracking_file = _project_root() / "backups" / "last_weekly_report.txt"
    if not tracking_file.exists():
        return "No weekly report tracking file found yet."

    try:
        content = tracking_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return f"Could not read weekly report tracking file: {exc}"

    return content or "Weekly report tracking file is empty."


def _latest_generated_pdf_info():
    output_dir = _generated_pdf_dir()
    pdf_files = list(output_dir.glob("*.pdf"))
    if not pdf_files:
        return "No manually generated PDFs found yet."

    latest_pdf = max(pdf_files, key=lambda item: item.stat().st_mtime)
    generated_at = datetime.fromtimestamp(latest_pdf.stat().st_mtime).strftime("%d %b %Y, %I:%M %p")
    return f"{latest_pdf.name} | {generated_at}"


def _print_direct_run_intro():
    print("--- PDF Generator Manual Runner ---")
    print("Last weekly report info:")
    print(f"  {_read_last_weekly_report_info()}")
    print("Last manually generated PDF:")
    print(f"  {_latest_generated_pdf_info()}")
    print("")


def _safe_input(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        print("")
        print("No input received. Exiting without generating a PDF.")
        return None


def _confirm(prompt, phrase):
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = _safe_input(f"{prompt} Type {phrase}: ")
    if confirmation is None:
        return False
    return confirmation == phrase


def _write_pdf_bytes(pdf_bytes, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    logger.info("PDF_GENERATOR | SAVED | Output=%s | Size=%s bytes", output_path, len(pdf_bytes))
    print(f"SUCCESS: PDF saved to {output_path}")


def _generate_weekly_report_pdf():
    from App.services.weekly_report_service import build_weekly_hr_report_context, render_weekly_hr_report_html

    context = build_weekly_hr_report_context()
    output_path = _generated_pdf_dir() / f"weekly_hr_report_{_timestamp()}.pdf"
    logger.info(
        "PDF_GENERATOR | DRY_RUN | Weekly report | Period=%s to %s | Requests=%s | Employees=%s | Output=%s",
        context["period_start"],
        context["period_end"],
        context["total_requests"],
        context["employee_count"],
        output_path,
    )

    print("")
    print("--- Weekly Report PDF Dry Run ---")
    print(f"Period: {context['period_start']} to {context['period_end']}")
    print(f"Total requests: {context['total_requests']}")
    print(f"Employees with activity: {context['employee_count']}")
    print(f"Output folder: {_generated_pdf_dir()}")
    print(f"Output file: {output_path.name}")
    print("Action: No PDF created yet.")
    print("")

    if not _confirm("Proceed to generate weekly report PDF?", "GENERATE_PDF"):
        logger.info("PDF_GENERATOR | CANCELLED | Weekly report PDF confirmation declined.")
        print("Cancelled. No PDF was generated.")
        return

    logger.info("PDF_GENERATOR | CONFIRMED | Weekly report PDF generation accepted.")
    html_content = render_weekly_hr_report_html(context)
    _write_pdf_bytes(generate_pdf_from_html(html_content), output_path)


def _resolve_template_path(path_text):
    candidate = Path(path_text.strip().strip('"'))
    if candidate.is_absolute():
        return candidate
    return _project_root() / candidate


def _render_template_or_read_html(template_path):
    from django.template.loader import render_to_string

    project_root = _project_root()
    templates_root = project_root / "templates"

    try:
        template_name = template_path.resolve().relative_to(templates_root.resolve()).as_posix()
        return render_to_string(template_name, {})
    except ValueError:
        return template_path.read_text(encoding="utf-8")


def _generate_custom_template_pdf():
    path_text = _safe_input("Enter HTML/template path: ")
    if path_text is None:
        return
    if not path_text:
        print("Cancelled. No path entered.")
        return

    template_path = _resolve_template_path(path_text)
    output_path = _generated_pdf_dir() / f"{_safe_file_stem(template_path.stem)}_{_timestamp()}.pdf"
    logger.info(
        "PDF_GENERATOR | DRY_RUN | Custom template | Input=%s | Exists=%s | Output=%s",
        template_path,
        template_path.exists(),
        output_path,
    )

    print("")
    print("--- Custom Template PDF Dry Run ---")
    print(f"Input path: {template_path}")
    print(f"Input exists: {'Yes' if template_path.exists() else 'No'}")
    print(f"Output folder: {_generated_pdf_dir()}")
    print(f"Output file: {output_path.name}")
    print("Action: No PDF created yet.")
    print("")

    if not template_path.exists():
        logger.warning("PDF_GENERATOR | BLOCKED | Custom template input missing | Input=%s", template_path)
        print("Stopped. Input file does not exist.")
        return

    if not _confirm("Proceed to generate this PDF?", "GENERATE_PDF"):
        logger.info("PDF_GENERATOR | CANCELLED | Custom template PDF confirmation declined | Input=%s", template_path)
        print("Cancelled. No PDF was generated.")
        return

    logger.info("PDF_GENERATOR | CONFIRMED | Custom template PDF generation accepted | Input=%s", template_path)
    html_content = _render_template_or_read_html(template_path)
    _write_pdf_bytes(generate_pdf_from_html(html_content), output_path)


def main():
    _setup_django_for_direct_run()

    logger.info("PDF_GENERATOR | MANUAL_RUN | Opened direct runner.")
    _print_direct_run_intro()
    print("What do you want to do?")
    print("1. Generate weekly report PDF")
    print("2. Generate PDF from another HTML/template")
    print("3. Exit")
    choice = _safe_input("Choose option 1, 2, or 3: ")
    if choice is None:
        return

    if choice == "1":
        logger.info("PDF_GENERATOR | OPTION | Weekly report selected.")
        _generate_weekly_report_pdf()
    elif choice == "2":
        logger.info("PDF_GENERATOR | OPTION | Custom template selected.")
        _generate_custom_template_pdf()
    elif choice == "3":
        logger.info("PDF_GENERATOR | OPTION | Exit selected.")
        print("Exited. No PDF was generated.")
    else:
        logger.warning("PDF_GENERATOR | OPTION | Invalid option selected | Value=%s", choice)
        print("Invalid option. No PDF was generated.")


if __name__ == "__main__":
    main()
