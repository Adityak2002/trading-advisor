import os
import sys

def convert_html_to_pdf(html_path, pdf_path):
    try:
        from xhtml2pdf import pisa
    except ImportError:
        print("Error: xhtml2pdf is not installed. Please run: pip install xhtml2pdf")
        sys.exit(1)

    # Open HTML file
    with open(html_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()

    # Open PDF file for writing
    with open(pdf_path, "w+b") as pdf_file:
        # Convert HTML to PDF
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)

    # Return True if successful, False otherwise
    return not pisa_status.err

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_file = os.path.join(base_dir, "docs", "guide.html")
    pdf_file = os.path.join(base_dir, "docs", "trading_system_guide.pdf")

    print(f"Compiling {html_file} -> {pdf_file} ...")
    success = convert_html_to_pdf(html_file, pdf_file)
    
    if success:
        print("Success! PDF generated successfully at docs/trading_system_guide.pdf")
    else:
        print("Error: Failed to compile HTML to PDF.")
        sys.exit(1)
