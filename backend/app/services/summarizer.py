import logging

logger = logging.getLogger(__name__)

_summarizer = None

def _get_summarizer():
    global _summarizer
    if _summarizer is None:
        try:
            from transformers import pipeline
            logger.info("Loading HuggingFace summarization pipeline (sshleifer/distilbart-cnn-12-6)...")
            # This is a small (~1.2GB) model that works very well for fast CPU inference.
            _summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
        except ImportError:
            logger.warning("transformers not installed. Summarization disabled.")
            return None
    return _summarizer

def summarize_text(text: str) -> str:
    """
    Summarizes the given text using a fast local LLM pipeline.
    It splits large text into chunks if it exceeds the model's token limit.
    """
    if not text.strip():
        return ""
        
    summarizer = _get_summarizer()
    if not summarizer:
        return text
        
    # The distilbart model max token length is 1024.
    # We will chunk by rough character count (approx 3.5 chars per token -> ~3500 chars).
    max_chunk_chars = 3000
    
    # Very simple chunking for summarization
    import textwrap
    chunks = textwrap.wrap(text, max_chunk_chars, break_long_words=False, replace_whitespace=False)
    
    summarized_chunks = []
    
    for chunk in chunks:
        # Avoid summarizing extremely short fragments
        if len(chunk) < 200:
            summarized_chunks.append(chunk)
            continue
            
        try:
            # We enforce a dynamic max_length based on input length to prevent errors
            input_length = len(chunk.split())
            max_len = min(130, max(30, int(input_length * 0.6)))
            min_len = min(30, int(input_length * 0.2))
            
            result = summarizer(chunk, max_length=max_len, min_length=min_len, do_sample=False)
            if result and len(result) > 0:
                summarized_chunks.append(result[0]['summary_text'])
        except Exception as e:
            logger.error(f"Summarization failed for chunk: {e}")
            summarized_chunks.append(chunk) # Fallback to original text
            
    return " ".join(summarized_chunks)
