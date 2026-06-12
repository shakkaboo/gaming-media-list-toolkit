class FetchError(Exception):
    def __init__(self, message: str, error_code: str, is_retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.is_retryable = is_retryable

class UnsafeURLError(FetchError):
    def __init__(self, message: str, error_code: str):
        super().__init__(message, error_code, is_retryable=False)

class UnsafeIPError(FetchError):
    def __init__(self, message: str):
        super().__init__(message, "unsafe_resolved_ip", is_retryable=False)

class DNSError(FetchError):
    def __init__(self, message: str, error_code: str = "dns_failed", is_retryable: bool = True):
        super().__init__(message, error_code, is_retryable)

class ResponseTooLargeError(FetchError):
    def __init__(self, message: str):
        super().__init__(message, "response_too_large", is_retryable=False)

class UnsupportedContentTypeError(FetchError):
    def __init__(self, message: str, error_code: str = "unsupported_content_type"):
        super().__init__(message, error_code, is_retryable=False)

class RedirectError(FetchError):
    def __init__(self, message: str, error_code: str):
        super().__init__(message, error_code, is_retryable=False)
