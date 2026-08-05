import feedparser
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def fetch_rss_feed(url: str, max_items: int = 5) -> list[str]:
    """
    Fetch an RSS feed, extract text from items, and return a list of texts.
    """
    logger.info(f"Fetching RSS feed from: {url}")
    feed = feedparser.parse(url)
    
    if feed.bozo:
        logger.error(f"Failed to parse RSS feed: {feed.bozo_exception}")
        raise ValueError(f"Could not parse RSS feed: {feed.bozo_exception}")
        
    texts = []
    for entry in feed.entries[:max_items]:
        title = entry.get('title', '')
        # Description or content
        description = entry.get('description', '')
        if 'content' in entry:
            description = entry.content[0].value
            
        soup = BeautifulSoup(description, 'html.parser')
        text_content = soup.get_text(separator='\n\n', strip=True)
        
        full_text = f"{title}\n\n{text_content}"
        texts.append(full_text)
        
    return texts
