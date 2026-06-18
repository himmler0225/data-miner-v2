"""
TikTok Signature Generation Library

This package provides signature generation for TikTok API requests:
- X-Bogus: Anti-scraping signature using RC4 encryption and custom base64
- X-Gnarly: ChaCha20-based encryption signature
"""

from .bogus import Signer
from .gnarly import get_X_Gnarly

__all__ = ['Signer', 'get_X_Gnarly']
