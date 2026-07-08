class HandbookException(Exception):
    """Base exception for Student Handbook errors."""
    pass

class HandbookNotFoundException(HandbookException):
    """Exception raised when a requested handbook section is not found."""
    def __init__(self, message="Handbook section not found"):
        self.message = message
        super().__init__(self.message)

class AIModelException(HandbookException):
    """Exception raised for errors during AI model inference."""
    def __init__(self, message="Error communicating with the AI model"):
        self.message = message
        super().__init__(self.message)
