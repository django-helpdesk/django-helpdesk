"""UItility functions facilitate making unit testing easier and less brittle."""

import email
import factory
import faker
import random
import re
import string
import unicodedata
from io import BytesIO
from email.message import Message
from email.mime.text import MIMEText
from numpy.random import randint
from PIL import Image
from typing import Tuple, Any, Optional
import typing


def strip_accents(text):
    """
    Strip accents from input String. (only works on Pythin 3

    :param text: The input string.
    :type text: String.

    :returns: The processed String.
    :rtype: String.
    """
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore')
    text = text.decode("utf-8")
    return str(text)


def text_to_id(text):
    """
    Convert input text to id.

    :param text: The input string.
    :type text: String.

    :returns: The processed String.
    :rtype: String.
    """
    text = strip_accents(text.lower())
    text = re.sub('[ ]+', '_', text)
    text = re.sub('[^0-9a-zA-Z_-]', '', text)
    return text


def get_random_string(length: int=16) -> str:
    return "".join(
        [random.choice(string.ascii_letters + string.digits) for _ in range(length)]
    )


def generate_random_image(image_format, array_dims):
    """
    Creates an image from a random array.
    
    :param image_format: An image format (PNG or JPEG).
    :param array_dims: A tuple with array dimensions.
    
    :returns: A byte string with encoded image
    :rtype: bytes
    """
    image_bytes = randint(low=0, high=255, size=array_dims, dtype='uint8')
    io = BytesIO()
    image_pil = Image.fromarray(image_bytes)
    image_pil.save(io, image_format, subsampling=0, quality=100)
    return io.getvalue()


def get_random_image(image_format: str="PNG", size: int=5):
    """
    Returns a random image.
    
    Args:
      image_format: An image format (PNG or JPEG).
    
    Returns:
      A string with encoded image
    """
    return generate_random_image(image_format, (size, size, 3))


def get_fake(provider: str, locale: str = "en_US", min_length: int = 5) -> Any:
    """
    Generates a random string, float, integer etc based on provider
    Provider can be "text', 'sentence',  
      e.g. `get_fake('name')` ==> 'Buzz Aldrin' 
    """
    return factory.Faker(provider).evaluate({}, None, {'locale': locale,})


def generate_email_address(
        locale: str="en_US",
        use_short_email: bool=False,
        real_name_format: Optional[str]="{last_name}, {first_name}",
        last_name_override: Optional[str]=None) -> Tuple[str, str, str, str]:
    '''
    Generate an RFC 2822 email address
    
    :param locale: change this to generate locale specific names
    :param use_short_email: defaults to false. If true then does not include real name in email address
    :param real_name_format: pass a different format if different than "{last_name}, {first_name}"
    :param last_name_override: override the fake name if you want some special characters in the last name
    :returns <RFC2822 formatted email for header>, <short email address>, <first name>, <last_name
    '''
    fake = faker.Faker(locale=locale)
    first_name = fake.first_name()
    last_name = last_name_override or fake.last_name()
    real_name = None if use_short_email else real_name_format.format(first_name=first_name, last_name=last_name)
    # Add a random string to ensure we do not generate a real domain name
    email_address = "{}.{}@{}".format(
        first_name.replace(' ', '').encode("ascii", "ignore").lower().decode(),
        last_name.replace(' ', '').encode("ascii", "ignore").lower().decode(),
        get_random_string(5) + fake.domain_name()
    )
    # format email address for RFC 2822 and return
    return email.utils.formataddr((real_name, email_address)), email_address, first_name, last_name


def generate_text_email(locale: str="en_US",
        content_type: str="text/plain",
        use_short_email: bool=False
        ) -> typing.Tuple[Message, typing.Tuple[str, str], typing.Tuple[str, str]]:
    """
    Generates an email including headers
    """
    to_meta = generate_email_address(locale, use_short_email=use_short_email)
    from_meta = generate_email_address(locale, use_short_email=use_short_email)
    body = get_fake("text", locale=locale)
    
    msg = MIMEText(body)
    msg['Subject'] = get_fake("sentence", locale=locale)
    msg['From'] = from_meta[0]
    msg['To'] = to_meta[0]
    return msg, from_meta, to_meta
