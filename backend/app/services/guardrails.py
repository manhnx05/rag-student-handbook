import re

class PromptInjectionGuardrail:
    """A simple heuristics-based guardrail to prevent basic prompt injections."""
    
    FORBIDDEN_PHRASES = [
        "ignore previous",
        "ignore all previous",
        "system prompt",
        "you are now",
        "forget all",
        "bypass",
        "act as a",
        "developer mode",
        "DAN", # Do Anything Now
    ]

    @classmethod
    def check_query(cls, query: str) -> bool:
        """
        Check if the query contains suspicious prompt injection patterns.
        Returns True if safe, False if suspicious.
        """
        query_lower = query.lower()
        
        for phrase in cls.FORBIDDEN_PHRASES:
            if phrase in query_lower:
                return False
                
        # Additionally, block extremely long inputs which can be used to overflow context
        if len(query) > 2000:
            return False
            
        return True
