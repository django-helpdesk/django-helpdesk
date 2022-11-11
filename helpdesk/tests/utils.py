"""UItility functions facilitate making unit testing easier and less brittle."""


from PIL import Image
import email
from email import encoders
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import factory
import faker
from io import BytesIO
from numpy.random import randint
import random
import re
import string
import typing
from typing import Any, Optional, Tuple
import unicodedata


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
    Provider can be "text', 'sentence', "word" 
      e.g. `get_fake('name')` ==> 'Buzz Aldrin' 
    """
    string = factory.Faker(provider).evaluate({}, None, {'locale': locale,})
    while len(string) < min_length:
        string += factory.Faker(provider).evaluate({}, None, {'locale': locale,})
    return string


def get_fake_html(locale: str = "en_US", wrap_in_body_tag=True) -> Any:
    """
    Generates a random string, float, integer etc based on provider
    Provider can be "text', 'sentence',  
      e.g. `get_fake('name')` ==> 'Buzz Aldrin' 
    """
    html = factory.Faker("sentence").evaluate({}, None, {'locale': locale,})
    for _ in range(0,4):
        html += "<li>" + factory.Faker("sentence").evaluate({}, None, {'locale': locale,}) + "</li>"
    for _ in range(0,4):
        html += "<p>" + factory.Faker("text").evaluate({}, None, {'locale': locale,})
    return f"<body>{html}</body>" if wrap_in_body_tag else html

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

def generate_file_mime_part(locale: str="en_US",filename: str = None) -> Message:
    """
    
    :param locale: change this to generate locale specific file name and attachment content
    :param filename: pass a file name if you want to specify a specific name otherwise a random name will be generated
    """
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(get_fake("text", locale=locale, min_length=1024))
    encoders.encode_base64(part)
    if not filename:
        filename = get_fake("word", locale=locale, min_length=8) + ".txt"
    part.add_header('Content-Disposition', "attachment; filename= %s" % filename)
    return part

def generate_image_mime_part(locale: str="en_US",imagename: str = None) -> Message:
    """
    
    :param locale: change this to generate locale specific file name and attachment content
    :param filename: pass a file name if you want to specify a specific name otherwise a random name will be generated
    """
    part = MIMEImage(generate_random_image(image_format="JPEG", array_dims=(200, 200)))
    part.set_payload(get_fake("text", locale=locale, min_length=1024))
    encoders.encode_base64(part)
    if not imagename:
        imagename = get_fake("word", locale=locale, min_length=8) + ".jpg"
    part.add_header('Content-Disposition', "attachment; filename= %s" % imagename)
    return part

def generate_email_list(address_cnt: int = 3,
        locale: str="en_US",
        use_short_email: bool=False
        ) -> str:
    """
    Generates a list of email addresses formatted for email headers on a Mime part
    
    :param address_cnt: the number of email addresses to string together
    :param locale: change this to generate locale specific "real names" and subject
    :param use_short_email: produces a email address without "real name" if True

    """
    email_address_list = [generate_email_address(locale, use_short_email=use_short_email)[0] for _ in range(0, address_cnt)]
    return ",".join(email_address_list)

def add_simple_email_headers(message: Message, locale: str="en_US",
        use_short_email: bool=False
        ) -> typing.Tuple[typing.Tuple[str, str], typing.Tuple[str, str]]:
    """
    Adds the key email headers to a Mime part
    
    :param message: the Mime part to add headers to
    :param locale: change this to generate locale specific "real names" and subject
    :param use_short_email: produces a "To" or "From" that is only the email address if True

    """
    to_meta = generate_email_address(locale, use_short_email=use_short_email)
    from_meta = generate_email_address(locale, use_short_email=use_short_email)
    
    message['Subject'] = get_fake("sentence", locale=locale)
    message['From'] = from_meta[0]
    message['To'] = to_meta[0]
    return from_meta, to_meta

def generate_mime_part(locale: str="en_US",
        part_type: str="plain",
        ) -> typing.Optional[Message]:
    """
    Generates amime part of the sepecified type
    
    :param locale: change this to generate locale specific strings
    :param text_type: options are plain, html, image (attachment), file (attachment)
    """
    if "plain" == part_type:
        body = get_fake("text", locale=locale, min_length=1024)
        msg = MIMEText(body)
    elif "html" == part_type:
        body = get_fake_html(locale=locale, wrap_in_body_tag=True)
        msg = MIMEText(body)
    elif "file" == part_type:
        msg = generate_file_mime_part(locale=locale)
    elif "image" == part_type:
        msg = generate_image_mime_part(locale=locale)
    else:
        raise Exception("Mime part not implemented: " + part_type)
    return msg

def generate_multipart_email(locale: str="en_US",
        type_list: typing.List[str]=["plain", "html", "attachment"],
        use_short_email: bool=False
        ) -> typing.Tuple[Message, typing.Tuple[str, str], typing.Tuple[str, str]]:
    """
    Generates an email including headers with the defined multiparts
    
    :param locale:
    :param type_list: options are plain, html, image (attachment), file (attachment)
    :param use_short_email: produces a "To" or "From" that is only the email address if True
    """    
    msg = MIMEMultipart()
    for part_type in type_list:
        msg.attach(generate_mime_part(locale=locale, part_type=part_type))
    from_meta, to_meta = add_simple_email_headers(msg, locale=locale, use_short_email=use_short_email)
    return msg, from_meta, to_meta

def generate_text_email(locale: str="en_US",
        use_short_email: bool=False
        ) -> typing.Tuple[Message, typing.Tuple[str, str], typing.Tuple[str, str]]:
    """
    Generates an email including headers
    """
    body = get_fake("text", locale=locale, min_length=1024)
    msg = MIMEText(body)
    from_meta, to_meta = add_simple_email_headers(msg, locale=locale, use_short_email=use_short_email)
    return msg, from_meta, to_meta

def generate_html_email(locale: str="en_US",
        use_short_email: bool=False
        ) -> typing.Tuple[Message, typing.Tuple[str, str], typing.Tuple[str, str]]:
    """
    Generates an email including headers
    """
    body = get_fake_html(locale=locale)
    msg = MIMEText(body)
    from_meta, to_meta = add_simple_email_headers(msg, locale=locale, use_short_email=use_short_email)
    return msg, from_meta, to_meta
