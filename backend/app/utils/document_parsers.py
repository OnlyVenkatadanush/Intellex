import io
import csv
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader

class DocumentParser:
    @staticmethod
    def parse_txt(content_bytes: bytes) -> str:
        """Parses plain text bytes."""
        return content_bytes.decode("utf-8", errors="ignore")

    @staticmethod
    def parse_csv(content_bytes: bytes) -> str:
        """Parses CSV bytes and formats as a Markdown table for LLM context reading."""
        try:
            text = content_bytes.decode("utf-8", errors="ignore")
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return "Empty CSV file"
            
            # Format as markdown table
            markdown_table = []
            header = rows[0]
            markdown_table.append("| " + " | ".join(header) + " |")
            markdown_table.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in rows[1:50]:  # Limit to first 50 rows to keep context length reasonable
                # Pad row values if needed
                padded_row = row + [""] * (len(header) - len(row))
                markdown_table.append("| " + " | ".join(padded_row) + " |")
            
            return "\n".join(markdown_table)
        except Exception as e:
            return f"Error parsing CSV file: {str(e)}"

    @staticmethod
    def parse_pdf(content_bytes: bytes) -> str:
        """Parses PDF using pypdf reader."""
        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n".join(text_parts)
        except Exception as e:
            return f"Error parsing PDF file: {str(e)}"

    @staticmethod
    def parse_docx(content_bytes: bytes) -> str:
        """
        Parses DOCX files by reading its underlying word/document.xml inside the zip.
        Avoids external dependencies like python-docx.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(content_bytes)) as docx_zip:
                # Read word/document.xml
                xml_content = docx_zip.read('word/document.xml')
                root = ET.fromstring(xml_content)
                
                # Namespace mapping
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                
                # Find all text elements w:t
                text_parts = []
                for p in root.findall('.//w:p', ns):
                    p_text = []
                    for t in p.findall('.//w:t', ns):
                        if t.text:
                            p_text.append(t.text)
                    if p_text:
                        text_parts.append("".join(p_text))
                
                return "\n".join(text_parts)
        except Exception as e:
            return f"Error parsing DOCX file: {str(e)}"

    @staticmethod
    def parse_image(filename: str, content_bytes: bytes) -> str:
        """Simulates OCR text extraction from figures or images."""
        return (
            f"[Image OCR Simulation]\n"
            f"Filename: {filename}\n"
            f"File Size: {len(content_bytes)} bytes\n"
            f"Extracted Metadata: Structural schematic. Diagram represents experimental metrics "
            f"and timeline parameters related to the research query."
        )

    @classmethod
    def parse_file(cls, filename: str, content_bytes: bytes) -> str:
        """Dispatches parsing to specialized parse handlers based on file extension."""
        ext = filename.split(".")[-1].lower()
        if ext == "txt":
            return cls.parse_txt(content_bytes)
        elif ext == "csv":
            return cls.parse_csv(content_bytes)
        elif ext == "pdf":
            return cls.parse_pdf(content_bytes)
        elif ext == "docx":
            return cls.parse_docx(content_bytes)
        elif ext in ["png", "jpg", "jpeg"]:
            return cls.parse_image(filename, content_bytes)
        
        # Default fallback
        return content_bytes.decode("utf-8", errors="ignore")
