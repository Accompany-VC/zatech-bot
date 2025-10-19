"""
Rate limiter security utility.

Handles:
- Rate limiting for login attempts
- IP-based tracking
- Security-related helper functions
"""

import logging
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)

class RateLimiter:
    """In-memory rate limiter for login attempts (AI was used to help write this class)."""

    def __init__(self, max_attempts: int=5, lockout_duration: int=900):  #Change values for production
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration  # in seconds
        self.attempts = {}  # {ip: (attempt_count, last_attempt_timestamp)}

    def is_rate_limited(self, ip: str) -> Tuple[bool, int]:
        """Check if given IP is rate limited."""

        if ip not in self.attempts:
            return False, 0
        
        attempts, last_attempt = self.attempts[ip]

        if attempts < self.max_attempts:
            return False, 0
        
        # Check if lockout has expired
        time_since_last = datetime.utcnow().timestamp() - last_attempt
        
        # If lockout expired, reset
        if time_since_last >= self.lockout_duration:
            del self.attempts[ip]
            return False, 0
        
        # Still locked out
        seconds_remaining = int(self.lockout_duration - time_since_last)
        logger.warning(f"Rate limit active for IP {ip} - {seconds_remaining}s remaining")
        return True, seconds_remaining
    
    def record_failure(self, ip: str) -> None:
        """Record a failed login attempt"""

        attempts, _ = self.attempts.get(ip, (0, 0))
        self.attempts[ip] = (attempts + 1, datetime.utcnow().timestamp())

        if attempts + 1 >= self.max_attempts:
            logger.warning(f"IP {ip} has been rate limited due to too many failed attempts")

    def reset_attempts(self, ip: str) -> None:
        """Reset the attempt count for an IP on successful login"""
        
        if ip in self.attempts:
            del self.attempts[ip]

    def get_attempt_count(self, ip: str) -> int:
        """Get the current attempt count for an IP"""
        
        attempts, _ = self.attempts.get(ip, (0, 0))
        return attempts
    
# Global instance
rate_limiter = RateLimiter(max_attempts=5, lockout_duration=900) 
