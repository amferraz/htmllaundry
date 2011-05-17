import re
import six
from lxml import etree
from lxml import html
from htmllaundry.cleaners import DocumentCleaner


TAG = re.compile(six.u('<.*?>'))
ANCHORS = etree.XPath('descendant-or-self::a | descendant-or-self::x:a',
                      namespaces={'x': html.XHTML_NAMESPACE})
ALL_WHITESPACE = re.compile(r'^\s*$', re.UNICODE)


def is_whitespace(txt):
    """Utility method to test if txt is all whitespace or None."""
    return txt is None or bool(ALL_WHITESPACE.match(txt))


def strip_markup(markup):
    """Strip all markup from a HTML fragment."""
    return TAG.sub(six.u(""), markup)


StripMarkup = strip_markup  # BBB for htmllaundry <2.0


def remove_element(el):
    parent = el.getparent()
    if el.tail:
        previous = el.getprevious()
        if previous is not None:
            if previous.tail:
                previous.tail += el.tail
            else:
                previous.tail = el.tail
        else:
            if parent.text:
                parent.text += el.tail
            else:
                parent.text = el.tail

    parent.remove(el)


def remove_empty_tags(doc):
    """Removes all empty tags from a HTML document. Javascript editors
    and browsers have a nasty habit of leaving stray tags around after
    their contents have been removed. This function removes all such
    empty tags, leaving only valid empty tags.

    In addition consecutive <br/> tags are folded into a single tag.
    This forces whitespace styling to be done using CSS instead of via an
    editor, which almost always produces better and more consistent results.
    """

    legal_empty_tags = frozenset(['br', 'hr', 'img', 'input'])

    if hasattr(doc, 'getroot'):
        doc = doc.getroot()

    def clean(doc):
        victims = []
        for el in doc.iter():
            if el.tag == 'br':
                preceding = el.getprevious()
                parent = el.getparent()

                if (preceding is None and not parent.text) or \
                        (preceding is not None and preceding.tag == el.tag \
                            and not preceding.tail) or \
                        (not el.tail and el.getnext() is None):
                    victims.append(el)
                    continue

            if el.tag in legal_empty_tags:
                continue

            if len(el) == 0 and is_whitespace(el.text):
                victims.append(el)
                continue

        if victims and victims[0] == doc:
            doc.clear()
            return 0
        else:
            for victim in victims:
                remove_element(victim)

        return len(victims)

    while clean(doc):
        pass

    return doc


def strip_outer_breaks(doc):
    """Remove any toplevel break elements."""
    victims = []

    for i in range(len(doc)):
        el = doc[i]
        if el.tag == 'br':
            victims.append(el)

    for victim in victims:
        remove_element(victim)


def wrap_text(doc, element='p'):
    """Make sure there is no unwrapped text at the top level. Any bare text
    found is wrapped in a `<p>` element.
    """
    def par(text):
        el = etree.Element(element)
        el.text = text
        return el

    if doc.text:
        doc.insert(0, par(doc.text))

    insertions = []
    for i in range(len(doc)):
        el = doc[i]
        if not is_whitespace(el.tail):
            insertions.append((i, par(el.tail)))
            el.tail = None

    for (index, el) in reversed(insertions):
        doc.insert(index + 1, el)


def sanitize(input, cleaner=DocumentCleaner, wrap='p'):
    """Cleanup markup using a given cleanup configuration.
       Unwrapped text will be wrapped with wrap parameter.
    """
    if 'body' not in cleaner.allow_tags:
        cleaner.allow_tags.append('body')

    input = six.u("<html><body>%s</body></html>") % input
    document = html.document_fromstring(input)
    bodies = [e for e in document if html._nons(e.tag) == 'body']
    body = bodies[0]

    cleaned = cleaner.clean_html(body)
    remove_empty_tags(cleaned)
    strip_outer_breaks(cleaned)

    if wrap is not None:
        if wrap in html.defs.tags:
            wrap_text(cleaned, wrap)
        else:
            raise ValueError(
                'Invalid html tag provided for wrapping the sanitized text')

    output = six.u('').join([etree.tostring(fragment, encoding=six.text_type)
        for fragment in cleaned.iterchildren()])
    if wrap is None and cleaned.text:
        output = cleaned.text + output

    return output
