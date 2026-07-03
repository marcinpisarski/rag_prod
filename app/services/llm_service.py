"""LLM service - answer generation with citations"""
import logging
import json
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from app.config import settings

logger = logging.getLogger(__name__)


class SourceReference(BaseModel):
    """Citation source reference"""
    document_id: str = Field(description="Document identifier")
    document_title: str = Field(description="Human-readable document title")
    page_number: int = Field(description="Page number in source")
    segment_id: int = Field(description="Segment identifier")
    excerpt: str = Field(description="Relevant excerpt from source")


class AnswerResponse(BaseModel):
    """Structured response with citations"""
    content: str = Field(description="Generated answer text")
    sources: List[SourceReference] = Field(default_factory=list, description="List of source citations")
    has_relevant_content: bool = Field(description="Whether answer is based on provided context")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")


class LLMService:
    """Handles LLM interactions for answer generation"""
    
    SYSTEM_INSTRUCTIONS = """You are a professional knowledge assistant with the following guidelines:

1. Answer ONLY using the provided context documents
2. If the context lacks necessary information, clearly state: "I don't have sufficient information to answer this question in the provided documents"
3. Cite your sources accurately - include which document and what specific section you're referencing
4. Be concise and professional in your responses
5. If multiple interpretations exist, explain the differences
6. Maintain factual accuracy - do not speculate or hallucinate

RESPONSE FORMAT:
Return a valid JSON object with:
{
  "content": "Your answer here",
  "sources": [
    {
      "document_id": "doc_id",
      "document_title": "Document Name",
      "page_number": 1,
      "segment_id": 0,
      "excerpt": "Relevant quote"
    }
  ],
  "has_relevant_content": true,
  "confidence": 0.85
}
"""
    
    def __init__(self):
        self.llm_provider = settings.llm_provider
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
    
    def generate_answer(self, question: str, context_segments: List[Dict]) -> AnswerResponse:
        """
        Generate an answer based on context segments.
        
        Args:
            question: User's question
            context_segments: Retrieved relevant segments with metadata
            
        Returns:
            AnswerResponse with citations
        """
        if self.llm_provider == "openai":
            return self._generate_with_openai(question, context_segments)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

    async def stream_answer_tokens(self, question: str, context_segments: List[Dict]):
        """Stream answer tokens for SSE responses."""
        if self.llm_provider != "openai":
            raise ValueError(f"Streaming not supported for provider: {self.llm_provider}")
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        context = self._format_context(context_segments)
        user_prompt = f"""Context Documents:
{context}

Question: {question}

Answer using only the context above. Be concise and cite document names when relevant."""

        stream = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a knowledge assistant. Answer only from provided context. If information is missing, say so clearly."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def build_answer_from_context(
        self,
        question: str,
        context_segments: List[Dict],
        content: str,
    ) -> AnswerResponse:
        """Build structured answer with citations from retrieved segments."""
        sources = []
        for seg in context_segments[:5]:
            excerpt = seg.get("text", "")[:300]
            sources.append(SourceReference(
                document_id=str(seg.get("document_id", "")),
                document_title=seg.get("document_title", "Unknown"),
                page_number=int(seg.get("page_number") or 0),
                segment_id=int(seg.get("segment_id") or 0),
                excerpt=excerpt,
            ))

        has_content = bool(content.strip()) and "don't have sufficient information" not in content.lower()
        return AnswerResponse(
            content=content.strip(),
            sources=sources,
            has_relevant_content=has_content and bool(context_segments),
            confidence=0.85 if has_content else 0.3,
        )
    
    def _format_context(self, segments: List[Dict]) -> str:
        """Format context segments for the prompt"""
        context_lines = []
        for i, seg in enumerate(segments):
            context_lines.append(
                f"[Source {i+1}] Document: {seg.get('document_title', 'Unknown')}, "
                f"Page: {seg.get('page_number', '?')}\n"
                f"Content: {seg['text']}\n"
            )
        return "\n---\n".join(context_lines)
    
    def _generate_with_openai(self, question: str, context_segments: List[Dict]) -> AnswerResponse:
        """Generate answer using OpenAI API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key)
            context = self._format_context(context_segments)
            
            user_prompt = f"""Context Documents:
{context}

Question: {question}

Please provide a structured response in JSON format as specified in your instructions."""
            
            logger.info(f"Calling LLM: {self.model}")
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse response
            response_text = response.choices[0].message.content
            response_data = json.loads(response_text)
            
            logger.info("LLM response generated successfully")
            
            # Convert to AnswerResponse
            answer = AnswerResponse(
                content=response_data.get("content", ""),
                sources=[
                    SourceReference(**src) for src in response_data.get("sources", [])
                ],
                has_relevant_content=response_data.get("has_relevant_content", False),
                confidence=float(response_data.get("confidence", 0.5))
            )
            
            return answer
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
