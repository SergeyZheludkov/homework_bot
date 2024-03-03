class APIRequestError(RuntimeError):
    """Exception class to report errors of API-service request."""


class CheckResponseError(TypeError):
    """Exception class to report errors of check API-response."""


class ParseError(KeyError):
    """Exception class to report errors of parse_status function."""


class SendMessageError(RuntimeError):
    """Exception class to report errors of message delivery to Telegram."""
