import random

def backoff(retry_step: int, base: int = 1, multiplier: int = 2, cap: int = 60, jitter: int = 3) -> int:
    """
    Exponential backoff with jitter.
    
    retry_step: current retry attempt (0-based)
    base: initial wait time in seconds
    multiplier: factor to multiply by each retry
    cap: maximum wait time in seconds
    jitter: max random variation in seconds
    
    Returns: number of seconds to wait before retrying
    """
    # Exponential growth
    timeout = base * (multiplier ** retry_step)
    
    # Cap the value
    timeout = min(timeout, cap)
    
    # Apply jitter (either positive or negative)
    timeout += random.randint(-jitter, jitter)
    
    # Avoid negative timeouts
    return max(0, timeout)
