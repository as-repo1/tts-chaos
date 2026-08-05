import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)

_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model 'all-MiniLM-L6-v2'...")
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            logger.warning("sentence-transformers not installed. Semantic features disabled.")
            return None
    return _model

_style_embeddings = None
_style_names = []

def detect_style(text: str) -> str:
    """Detects the best matching style from predefined emotional styles."""
    model = _get_model()
    if not model:
        return "neutral"
        
    global _style_embeddings, _style_names
    
    if _style_embeddings is None:
        from backend.app.services.voice_styles import STYLE_PRESETS
        _style_names = list(STYLE_PRESETS.keys())
        descriptions = [
            f"This text is spoken in a {s} tone of voice." for s in _style_names
        ]
        _style_embeddings = model.encode(descriptions)
        
    text_embedding = model.encode([text])[0]
    
    similarities = np.dot(_style_embeddings, text_embedding) / (
        np.linalg.norm(_style_embeddings, axis=1) * np.linalg.norm(text_embedding)
    )
    
    best_idx = int(np.argmax(similarities))
    return _style_names[best_idx]


def semantic_chunking(text: str, max_chars: int = 1500) -> List[str]:
    """
    Splits text semantically. It splits by sentences first, then measures cosine similarity 
    between consecutive sentences. It chunks at the points of lowest similarity (topic shifts)
    while respecting the max_chars limit.
    """
    model = _get_model()
    if not model:
        from backend.app.services.batch_generator import chunk_text
        return chunk_text(text, max_chars)
        
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return []
        
    if len(sentences) == 1:
        if len(sentences[0]) > max_chars:
            from backend.app.services.batch_generator import chunk_text
            return chunk_text(text, max_chars)
        return sentences
        
    embeddings = model.encode(sentences)
    
    similarities = []
    for i in range(len(embeddings) - 1):
        # Handle zero vectors safely
        norm_a = np.linalg.norm(embeddings[i])
        norm_b = np.linalg.norm(embeddings[i+1])
        if norm_a == 0 or norm_b == 0:
            similarities.append(0.0)
        else:
            sim = np.dot(embeddings[i], embeddings[i+1]) / (norm_a * norm_b)
            similarities.append(sim)
        
    chunks = []
    current_chunk = sentences[0]
    
    for i in range(len(similarities)):
        sentence = sentences[i+1]
        sim = similarities[i]
        
        topic_shift = sim < 0.25
        exceeds_limit = len(current_chunk) + len(sentence) + 1 > max_chars
        
        if exceeds_limit or (topic_shift and len(current_chunk) > 200):
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk += " " + sentence
            
    if current_chunk:
        chunks.append(current_chunk)
        
    final_chunks = []
    from backend.app.services.batch_generator import chunk_text
    for c in chunks:
        if len(c) > max_chars:
            final_chunks.extend(chunk_text(c, max_chars))
        else:
            final_chunks.append(c)
            
    return final_chunks
