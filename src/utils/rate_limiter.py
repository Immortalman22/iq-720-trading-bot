"""Rate limiting implementation for API endpoints."""
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10

class RateLimiter:
    """Rate limiter implementation using token bucket algorithm."""
    
    def __init__(self, config: RateLimitConfig = RateLimitConfig()):
        self.config = config
        self.requests: Dict[str, list[float]] = defaultdict(list)
        # Initialize buckets at maximum capacity
        self.minute_buckets: Dict[str, float] = defaultdict(lambda: config.requests_per_minute)
        self.hour_buckets: Dict[str, float] = defaultdict(lambda: config.requests_per_hour)
        self.last_refill: Dict[str, float] = defaultdict(float)
    
    def _cleanup_old_requests(self, ip: str) -> None:
        """Remove requests older than 1 hour."""
        current_time = time.time()
        cutoff = current_time - 3600  # 1 hour ago
        self.requests[ip] = [t for t in self.requests[ip] if t > cutoff]
    
    def _refill_buckets(self, ip: str) -> None:
        """Refill token buckets based on elapsed time."""
        current_time = time.time()
        time_passed = current_time - self.last_refill[ip]
        
        # Only refill if some time has passed
        if time_passed > 0:
            # Refill minute bucket
            minute_tokens = time_passed * (self.config.requests_per_minute / 60)
            self.minute_buckets[ip] = min(
                self.config.requests_per_minute,
                self.minute_buckets[ip] + minute_tokens
            )
            
            # Refill hour bucket
            hour_tokens = time_passed * (self.config.requests_per_hour / 3600)
            self.hour_buckets[ip] = min(
                self.config.requests_per_hour,
                self.hour_buckets[ip] + hour_tokens
            )
            
            self.last_refill[ip] = current_time
    
    def check_rate_limit(self, ip: str) -> Tuple[bool, Dict[str, int]]:
        """Check if request is within rate limits.
        
        Returns:
            Tuple[bool, Dict[str, int]]: (is_allowed, limits_info)
            where limits_info contains remaining requests for different time windows
        """
        current_time = time.time()
        self._cleanup_old_requests(ip)
        self._refill_buckets(ip)
        
        # Check burst limit (requests in last second)
        recent_requests = len([t for t in self.requests[ip] 
                             if t > current_time - 1])
        if recent_requests >= self.config.burst_limit:
            return False, self._get_limits_info(ip)
        
        # Check minute limit
        minute_requests = len([t for t in self.requests[ip]
                             if t > current_time - 60])
        if minute_requests >= self.config.requests_per_minute:
            return False, self._get_limits_info(ip)
        
        # Check hour limit
        hour_requests = len([t for t in self.requests[ip]
                           if t > current_time - 3600])
        if hour_requests >= self.config.requests_per_hour:
            return False, self._get_limits_info(ip)
        
        # All checks passed, record the request
        self.requests[ip].append(current_time)
        return True, self._get_limits_info(ip)
    
    def _get_limits_info(self, ip: str) -> Dict[str, int]:
        """Get information about remaining limits."""
        current_time = time.time()
        minute_requests = len([t for t in self.requests[ip]
                             if t > current_time - 60])
        hour_requests = len([t for t in self.requests[ip]
                           if t > current_time - 3600])
        burst_requests = len([t for t in self.requests[ip]
                            if t > current_time - 1])
                            
        return {
            "minute_remaining": max(0, self.config.requests_per_minute - minute_requests),
            "hour_remaining": max(0, self.config.requests_per_hour - hour_requests),
            "burst_remaining": max(0, self.config.burst_limit - burst_requests)
        }
