class IgnoreTicketException(Exception):
    """
    Raised when an email message is received from a sender who is marked to be ignored
    """
    pass