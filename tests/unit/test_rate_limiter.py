"""Test suite for rate limiter implementation."""
import time
import unittest
from src.utils.rate_limiter import RateLimiter, RateLimitConfig

class TestRateLimiter(unittest.TestCase):
    """Test cases for RateLimiter class."""
    
    def setUp(self):
        """Set up test cases."""
        self.config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=1000,
            burst_limit=10
        )
        self.limiter = RateLimiter(self.config)
        self.test_ip = "127.0.0.1"
    
    def test_basic_rate_limit(self):
        """Test basic rate limiting functionality."""
        # First request should be allowed
        allowed, info = self.limiter.check_rate_limit(self.test_ip)
        self.assertTrue(allowed)
        self.assertEqual(info["minute_remaining"], 59)
        
        # Make 9 more requests (total 10, hitting burst limit)
        for _ in range(9):
            self.limiter.check_rate_limit(self.test_ip)
            
        # 11th request should be denied due to burst limit
        allowed, info = self.limiter.check_rate_limit(self.test_ip)
        self.assertFalse(allowed)
        self.assertEqual(info["burst_remaining"], 0)
    
    def test_minute_limit(self):
        """Test minute-based rate limiting."""
        # Make requests in bursts to test minute limit while avoiding burst limit
        for batch in range(6):  # 6 batches of 10 requests = 60 total
            # Make 10 requests quickly
            for _ in range(10):
                allowed, info = self.limiter.check_rate_limit(self.test_ip)
                self.assertTrue(allowed, 
                    f"Request in batch {batch} failed with info: {info}")
            
            # Wait 1.1 seconds between batches to reset burst limit
            if batch < 5:  # Don't wait after the last batch
                time.sleep(1.1)
        
        # Now bucket should be empty
        allowed, info = self.limiter.check_rate_limit(self.test_ip)
        self.assertFalse(allowed, 
            f"Request should be denied after 60 requests. Info: {info}")
        self.assertEqual(info["minute_remaining"], 0, 
            f"Expected minute_remaining = 0, got {info}")
    
    def test_bucket_refill(self):
        """Test request tracking over time."""
        # Make 10 requests
        for _ in range(10):
            allowed, info = self.limiter.check_rate_limit(self.test_ip)
            self.assertTrue(allowed)
        
        # Verify we used 10 requests
        _, info = self.limiter.check_rate_limit(self.test_ip)
        self.assertEqual(info["minute_remaining"], 50)
        
        # Wait for the burst window to expire
        time.sleep(1.1)
        
        # Should allow new requests
        allowed, info = self.limiter.check_rate_limit(self.test_ip)
        self.assertTrue(allowed)
        self.assertEqual(info["minute_remaining"], 49)
        
if __name__ == '__main__':
    unittest.main()
