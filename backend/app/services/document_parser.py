import io
from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub
from pypdf import PdfReader
import logging

logger = logging.getLogger(__name__)

def parse_document(file_bytes: bytes, filename: str) -> str:
    """
    Extract text from a document based on its extension.
    Supported extensions: .txt, .pdf, .epub
    """
    ext = filename.lower().split('.')[-1]
    
    if ext == 'txt':
        return file_bytes.decode('utf-8', errors='replace')
        
    elif ext in ('md', 'markdown'):
        import re
        text = file_bytes.decode('utf-8', errors='replace')
        # Strip markdown syntax for better TTS reading
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text) # links
        text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text) # bold
        text = re.sub(r'(\*|_)(.*?)\1', r'\2', text) # italics
        text = re.sub(r'#+\s+', '', text) # headers
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL) # code blocks
        text = re.sub(r'`(.*?)`', r'\1', text) # inline code
        text = re.sub(r'>\s+', '', text) # blockquotes
        return text
        
    elif ext == 'pdf':
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            return "\n\n".join(text)
        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            raise ValueError(f"Could not parse PDF file: {e}")
            
    elif ext == 'epub':
        try:
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

            try:
                book = epub.read_epub(temp_path)

                chapters = []
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        content = item.get_content()
                        soup = BeautifulSoup(content, 'html.parser')
                        text = soup.get_text(separator='\n\n', strip=True)
                        if text:
                            chapters.append(text)
            finally:
                os.unlink(temp_path)
            return "\n\n---\n\n".join(chapters)
            
        except Exception as e:
            logger.error(f"Failed to parse EPUB: {e}")
            raise ValueError(f"Could not parse EPUB file: {e}")
            
    else:
        raise ValueError(f"Unsupported file format: {ext}")
