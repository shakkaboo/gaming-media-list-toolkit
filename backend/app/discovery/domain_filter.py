from typing import Optional, Set
from app.discovery.blocklists import (
    SOCIAL_MEDIA_BLOCKS, VIDEO_STREAMING_BLOCKS, FORUM_BLOCKS,
    SEARCH_ENGINE_BLOCKS, MARKETPLACE_BLOCKS, SHORTENER_BLOCKS,
    DEFAULT_DOMAIN_BLOCKS
)

def get_block_reason(full_host: str, additional_blocks: Optional[Set[str]] = None) -> Optional[str]:
    """
    Checks if a host or any of its parent domains are blocked.
    Returns the reason code if blocked, otherwise None.
    """
    parts = full_host.lower().split(".")
    
    for i in range(len(parts)):
        sub = ".".join(parts[i:])
        
        if sub in SOCIAL_MEDIA_BLOCKS:
            return "blocked_social"
        if sub in VIDEO_STREAMING_BLOCKS:
            return "blocked_video"
        if sub in FORUM_BLOCKS:
            return "blocked_forum"
        if sub in SEARCH_ENGINE_BLOCKS:
            return "blocked_search_engine"
        if sub in MARKETPLACE_BLOCKS:
            return "blocked_marketplace"
        if sub in SHORTENER_BLOCKS:
            return "blocked_shortener"
        if sub in DEFAULT_DOMAIN_BLOCKS:
            return "blocked_domain"
            
        if additional_blocks and sub in additional_blocks:
            return "blocked_domain"
            
    return None
