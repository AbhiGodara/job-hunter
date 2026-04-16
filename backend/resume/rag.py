"""
RAG (Retrieval-Augmented Generation) pipeline for resume processing.

Chunks the resume into semantic sections, embeds them into ChromaDB,
and provides retrieval capabilities for the AI agents.
"""
import logging
import re
import hashlib
import os
from typing import List, Dict, Optional

log = logging.getLogger(__name__)

# Lazy-loaded globals
_chroma_client = None
_embedding_fn = None


def _get_embedding_function():
    """Lazy-load the sentence-transformers embedding function."""
    global _embedding_fn
    if _embedding_fn is None:
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            _embedding_fn = SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            log.info("Loaded embedding model: all-MiniLM-L6-v2")
        except Exception as e:
            log.error(f"Failed to load embedding model: {e}")
            raise
    return _embedding_fn


def _get_chroma_client():
    """Lazy-load ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            db_path = os.path.join(os.path.dirname(__file__), "../../data/chroma_db")
            os.makedirs(db_path, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=db_path)
            log.info(f"ChromaDB initialized at {db_path}")
        except Exception as e:
            log.error(f"Failed to initialize ChromaDB: {e}")
            raise
    return _chroma_client


def chunk_resume(resume_text: str) -> List[Dict[str, str]]:
    """
    Split resume text into semantic chunks by section headers.
    
    Identifies common resume sections (Experience, Education, Skills, etc.)
    and splits accordingly. Each chunk gets a section label and content.
    
    Returns:
        List of dicts with 'section' and 'content' keys.
    """
    if not resume_text or len(resume_text.strip()) < 50:
        return [{"section": "full_resume", "content": resume_text}]

    # Common section headers in resumes
    section_patterns = [
        r"(?i)(?:^|\n)\s*(?:professional\s+)?summary",
        r"(?i)(?:^|\n)\s*(?:work\s+)?experience",
        r"(?i)(?:^|\n)\s*(?:technical\s+)?skills",
        r"(?i)(?:^|\n)\s*education",
        r"(?i)(?:^|\n)\s*projects?",
        r"(?i)(?:^|\n)\s*certifications?",
        r"(?i)(?:^|\n)\s*achievements?",
        r"(?i)(?:^|\n)\s*publications?",
        r"(?i)(?:^|\n)\s*awards?",
        r"(?i)(?:^|\n)\s*languages?",
        r"(?i)(?:^|\n)\s*interests?",
        r"(?i)(?:^|\n)\s*objective",
        r"(?i)(?:^|\n)\s*profile",
    ]

    # Find all section header positions
    splits = []
    for pattern in section_patterns:
        for match in re.finditer(pattern, resume_text):
            splits.append(match.start())

    if not splits:
        # No recognizable sections → return as single chunk
        return [{"section": "full_resume", "content": resume_text}]

    splits = sorted(set(splits))

    # Add end of text
    splits.append(len(resume_text))

    # Extract contact info (everything before first section)
    chunks = []
    if splits[0] > 20:
        contact_text = resume_text[:splits[0]].strip()
        if contact_text:
            chunks.append({"section": "contact_info", "content": contact_text})

    # Extract each section
    for i in range(len(splits) - 1):
        section_text = resume_text[splits[i]:splits[i + 1]].strip()
        if not section_text or len(section_text) < 10:
            continue

        # Detect section name from first line
        first_line = section_text.split("\n")[0].strip().lower()
        first_line = re.sub(r"[^a-z\s]", "", first_line).strip()

        section_name = "other"
        if "experience" in first_line or "work" in first_line:
            section_name = "experience"
        elif "skill" in first_line or "technical" in first_line:
            section_name = "skills"
        elif "education" in first_line:
            section_name = "education"
        elif "project" in first_line:
            section_name = "projects"
        elif "summary" in first_line or "profile" in first_line or "objective" in first_line:
            section_name = "summary"
        elif "certification" in first_line:
            section_name = "certifications"
        elif "achievement" in first_line or "award" in first_line:
            section_name = "achievements"

        chunks.append({"section": section_name, "content": section_text})

    if not chunks:
        return [{"section": "full_resume", "content": resume_text}]

    log.info(f"Resume chunked into {len(chunks)} sections: {[c['section'] for c in chunks]}")
    return chunks


def embed_resume(resume_text: str, run_id: str) -> str:
    """
    Chunk and embed a resume into ChromaDB.
    
    Args:
        resume_text: Raw resume text
        run_id: Unique identifier for this search run
        
    Returns:
        Collection name used for storage
    """
    collection_name = f"resume_{run_id}"

    try:
        client = _get_chroma_client()
        embed_fn = _get_embedding_function()

        # Delete existing collection if any
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        chunks = chunk_resume(resume_text)

        # Add chunks to collection
        ids = []
        documents = []
        metadatas = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{run_id}_chunk_{i}"
            ids.append(chunk_id)
            documents.append(chunk["content"])
            metadatas.append({"section": chunk["section"], "index": i})

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        log.info(f"Embedded {len(chunks)} resume chunks into collection '{collection_name}'")

        return collection_name

    except Exception as e:
        log.error(f"Resume embedding failed: {e}")
        return ""


def retrieve_resume_context(run_id: str, job_description: str, top_k: int = 10) -> str:
    """
    Retrieve the full resume content from ChromaDB, ordered by relevance
    to the given job description.
    
    This retrieves ALL chunks (not just top-k) but orders them by
    relevance to the JD so the most important sections come first
    in the LLM context window.
    
    Args:
        run_id: The run ID used during embedding
        job_description: The target job description text
        top_k: Number of chunks to retrieve
        
    Returns:
        Concatenated resume text, ordered by JD relevance.
    """
    collection_name = f"resume_{run_id}"

    try:
        client = _get_chroma_client()
        embed_fn = _get_embedding_function()

        collection = client.get_collection(
            name=collection_name,
            embedding_function=embed_fn,
        )

        # Query with JD to get relevance-ordered chunks
        results = collection.query(
            query_texts=[job_description],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        if not results or not results["documents"] or not results["documents"][0]:
            log.warning(f"No chunks found in collection {collection_name}")
            return ""

        # Build context with section labels
        context_parts = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            section = meta.get("section", "unknown").replace("_", " ").title()
            similarity = round(1 - dist, 3)  # cosine distance → similarity
            context_parts.append(f"[{section}] (relevance: {similarity})\n{doc}")

        full_context = "\n\n---\n\n".join(context_parts)
        log.info(f"Retrieved {len(context_parts)} resume chunks for JD matching")
        return full_context

    except Exception as e:
        log.warning(f"Resume retrieval failed (falling back to raw text): {e}")
        return ""
