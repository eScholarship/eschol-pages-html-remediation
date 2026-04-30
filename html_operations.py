from bs4 import BeautifulSoup
from html5lib import HTMLParser, parse


def validate_html(html):
    html = f"<!doctype html><html>{html}</html>"
    parser = HTMLParser(strict=True)
    try:
        parser.parse(html)
        return True
    except Exception as e:
        return False


def remove_empty_elements(bad_html: str):
    """
    Remediates HTML for accesibility. Loops the elements,
    finding and removing all zero-text-length elements,
    excluding certain self-closing tags: br, hr, img.

    :param bad_html: HTML with empty elements
    :return: Remediated HTML, semicolon-delimited string of empty elements
    """
    soup = BeautifulSoup(bad_html, 'html.parser')
    empty_elements = []

    for html_element in soup.find_all():
        if (len(html_element.get_text(strip=True)) == 0
                and html_element.name not in ['br', 'img', 'hr']):
            print(f"Element with text length: {html_element}")
            if len(html_element.contents) > 0 and html_element.name != 'a':
                print("Element includes children, removing duplicates and bubbling up.")

                # Bubble child elements to parent level, remove parent.
                html_element.unwrap()
                html_element.decompose()
            else:
                empty_elements.append(html_element.name)
                html_element.decompose()

    # Don't need to save the HTML if there's nothing to remediate
    if not empty_elements:
        soup = None

    return soup, empty_elements


def remove_empty_elements_safe(bad_html: str):
    """
    A safer version of the above function. Removes only top-level
    empty elements, and reports on potential nested empties.

    :param bad_html: HTML with empty elements
    :return: Remediated HTML, semicolon-delimited string of empty elements
    """
    soup = BeautifulSoup(bad_html, 'html.parser')
    empty_elements = []
    empty_elements_with_children = []

    for html_element in soup.find_all():
        if (len(html_element.get_text(strip=True)) == 0
                and html_element.name not in ['br', 'img', 'hr']):
            print(f"Element with text length: {html_element}")
            if len(html_element.contents) > 0:
                print("Element includes children. Noting but not removing.")
                empty_elements_with_children.append(html_element.name)
            else:
                print("Top-level element with no text or children. Removing")
                empty_elements.append(html_element.name)
                html_element.decompose()

    # Don't need to save the HTML if there's nothing to remediate
    if not empty_elements:
        soup = None

    return soup, empty_elements, empty_elements_with_children


def remove_newlines(pages, html_field):
    """To facilitate export, replaces newlines with spaces."""
    for page in pages:
        page[html_field] = (str(page[html_field])).replace('\n', ' ')

    return pages