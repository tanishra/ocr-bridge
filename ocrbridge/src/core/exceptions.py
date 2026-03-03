class OCRBridgeException(Exception):
    """Base exception for OCRBridge"""
    pass


class OCRFailedException(OCRBridgeException):
    """OCR processing failed"""
    pass


class InvalidReceiptException(OCRBridgeException):
    """Receipt format not recognized"""
    pass


class ExportFailedException(OCRBridgeException):
    """Export to destination failed"""
    pass


# Backward compatibility
ParchiException = OCRBridgeException
