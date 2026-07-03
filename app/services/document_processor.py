"""Document processing service - extraction and chunking"""
import logging
from typing import List, Dict, Optional
import PyPDF2
from app.config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document parsing, extraction, and segmentation"""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.document_chunk_size
        self.chunk_overlap = chunk_overlap or settings.document_chunk_overlap
    
    def extract_from_pdf(self, file_path: str) -> List[Dict]:
        """
        Extract text from PDF file into pages.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            List of dictionaries with page_number and text_content
        """
        pages = []
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if text.strip():
                        pages.append({
                            'page_number': page_num,
                            'text_content': text
                        })
                logger.info(f"Extracted {len(pages)} pages from {file_path}")
        except Exception as e:
            logger.error(f"Failed to extract PDF: {e}")
            raise
        
        return pages
    
    def extract_from_text(self, file_path: str) -> List[Dict]:
        """
        Extract text from plain text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            List with single dictionary containing full text as one page
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            logger.info(f"Extracted text from {file_path}")
            return [{
                'page_number': 1,
                'text_content': text
            }]
        except Exception as e:
            logger.error(f"Failed to extract text: {e}")
            raise
    
    def segment_content(self, pages: List[Dict]) -> List[Dict]:
        """
        Split pages into overlapping segments for semantic search.
        
        Args:
            pages: List of page dictionaries with text_content
            
        Returns:
            List of segment dictionaries with metadata
        """
        segments = []
        
        for page_dict in pages:
            page_number = page_dict['page_number']
            text = page_dict['text_content']
            
            # Create overlapping segments
            segment_index = 0
            start_pos = 0
            
            while start_pos < len(text):
                end_pos = min(start_pos + self.chunk_size, len(text))
                segment_text = text[start_pos:end_pos]
                
                if segment_text.strip():
                    segments.append({
                        'page_number': page_number,
                        'segment_index': segment_index,
                        'text_content': segment_text,
                        'segment_metadata': {
                            'start_char': start_pos,
                            'end_char': end_pos,
                            'length': len(segment_text)
                        }
                    })
                
                # Move to next segment with overlap
                start_pos += self.chunk_size - self.chunk_overlap
                segment_index += 1
        
        logger.info(f"Created {len(segments)} segments from {len(pages)} pages")
        return segments
    
    def process_file(self, file_path: str, file_type: str) -> List[Dict]:
        """
        Complete processing pipeline: extract and segment.
        
        Args:
            file_path: Path to file
            file_type: Type of file (pdf, txt, md)
            
        Returns:
            List of processed segments ready for embedding
        """
        # Extract based on file type
        if file_type.lower() == 'pdf':
            pages = self.extract_from_pdf(file_path)
        elif file_type.lower() in ['txt', 'text', 'md', 'markdown']:
            pages = self.extract_from_text(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Segment the extracted content
        segments = self.segment_content(pages)
        
        return segments
