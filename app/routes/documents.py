"""Routes for document management"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import Optional
import os
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base, KnowledgeBase, ContentSegment, SemanticEmbedding
from app.services import DocumentProcessor, EmbeddingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def process_document_background(doc_id: str, file_path: str):
    """Background task to process uploaded document"""
    db = SessionLocal()
    try:
        logger.info(f"Starting background processing for document {doc_id}")
        
        # Update status
        doc = db.query(KnowledgeBase).filter(KnowledgeBase.id == doc_id).first()
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return
        
        doc.status = "processing"
        db.commit()
        
        # Extract file type
        file_ext = file_path.split('.')[-1].lower()
        
        # Process document
        processor = DocumentProcessor()
        segments = processor.process_file(file_path, file_ext)
        
        # Generate embeddings
        embedding_svc = EmbeddingService()
        texts = [seg['text_content'] for seg in segments]
        embeddings = embedding_svc.embed_batch(texts)
        
        # Save segments and embeddings to database
        for segment_data, embedding in zip(segments, embeddings):
            seg = ContentSegment(
                document_id=doc_id,
                page_number=segment_data['page_number'],
                segment_index=segment_data['segment_index'],
                text_content=segment_data['text_content'],
                segment_metadata=segment_data['segment_metadata']
            )
            db.add(seg)
            db.flush()
            
            # Save embedding
            emb = SemanticEmbedding(
                segment_id=seg.id,
                vector_data=embedding.tolist() if hasattr(embedding, 'tolist') else embedding,
                embedding_model=embedding_svc.model_name
            )
            db.add(emb)
        
        db.commit()
        
        # Update document status
        doc.status = "ready"
        db.commit()
        
        logger.info(f"Successfully processed document {doc_id}: {len(segments)} segments")
        
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {e}")
        doc = db.query(KnowledgeBase).filter(KnowledgeBase.id == doc_id).first()
        if doc:
            doc.status = "failed"
            db.commit()
    finally:
        db.close()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    description: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Upload and process a document for indexing.
    
    Supported formats: PDF, TXT, MD
    Processing happens asynchronously in the background.
    """
    try:
        # Validate file type
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in ['pdf', 'txt', 'md', 'text', 'markdown']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Supported: pdf, txt, md"
            )
        
        # Create document record
        doc_id = str(uuid.uuid4())
        doc_title = title or file.filename
        
        db = SessionLocal()
        try:
            # Save file
            upload_dir = "/tmp/kb_documents"
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, f"{doc_id}_{file.filename}")
            
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Create database entry
            doc = KnowledgeBase(
                id=doc_id,
                title=doc_title,
                description=description,
                document_type=file_ext,
                file_path=file_path,
                status="pending"
            )
            db.add(doc)
            db.commit()
            
            # Schedule background processing
            background_tasks.add_task(process_document_background, doc_id, file_path)
            
            logger.info(f"Document {doc_id} uploaded and queued for processing")
            
            return {
                "document_id": doc_id,
                "title": doc_title,
                "status": "pending",
                "message": "Document uploaded and queued for indexing"
            }
        finally:
            db.close()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")


@router.get("/{doc_id}/status")
async def get_document_status(doc_id: str):
    """Get the status of a document"""
    db = SessionLocal()
    try:
        doc = db.query(KnowledgeBase).filter(KnowledgeBase.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        segment_count = db.query(ContentSegment).filter(
            ContentSegment.document_id == doc_id
        ).count()
        
        return {
            "document_id": doc_id,
            "title": doc.title,
            "status": doc.status,
            "document_type": doc.document_type,
            "segment_count": segment_count,
            "indexed_at": doc.indexed_at
        }
    finally:
        db.close()


@router.get("/")
async def list_documents():
    """List all indexed documents"""
    db = SessionLocal()
    try:
        documents = db.query(KnowledgeBase).all()
        results = []
        
        for doc in documents:
            segment_count = db.query(ContentSegment).filter(
                ContentSegment.document_id == doc.id
            ).count()
            results.append({
                "document_id": doc.id,
                "title": doc.title,
                "status": doc.status,
                "segment_count": segment_count,
                "indexed_at": doc.indexed_at
            })
        
        return {"documents": results, "total": len(results)}
    finally:
        db.close()
