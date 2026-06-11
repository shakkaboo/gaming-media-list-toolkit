import logging
import os
from urllib.parse import urlparse, urljoin

def setup_logger(name="media_list_generator", log_file="logs/app.log", level=logging.INFO):
    """Sets up a logger with file and console handlers."""
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if logger already exists
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # File Handler
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger

def clean_url(url):
    """Ensures a URL is properly formatted."""
    if not url or str(url).lower() == 'nan':
        return ""
    
    url = str(url).strip()
    if not url.startswith('http'):
        url = 'https://' + url
    
    return url

def make_absolute_url(base_url, relative_url):
    """Converts a relative URL to absolute based on the base_url."""
    if not relative_url:
        return ""
    if relative_url.startswith('http'):
        return relative_url
    return urljoin(base_url, relative_url)
