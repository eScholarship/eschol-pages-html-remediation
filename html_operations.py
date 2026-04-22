from bs4 import BeautifulSoup


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


def remove_newlines(pages):
    """To facilitate export, replaces newlines with spaces."""
    for page in pages:
        page['html'] = page['html'].replace('\n', ' ')
        page['remediated_html'] = (str(page['remediated_html'])).replace('\n', ' ')

    return pages
