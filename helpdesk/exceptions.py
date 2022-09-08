class IgnoreTicketException(Exception):
    """
    Raised when an email message is received from a sender who is marked to be ignored
    """
    pass


class DeleteIgnoredTicketException(Exception):
    """
    Raised when an email message is received from a sender who is marked to be ignored
    and the record is tagged to delete the email from the inbox
    """
    pass
