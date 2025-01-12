"""Helpers for writing unit tests."""

from __future__ import print_function, division, absolute_import
from fontTools.misc.py23 import *
from fontTools.misc.xmlWriter import XMLWriter


def parseXML(xmlSnippet):
    """Parses a snippet of XML.

    The result is in the same format that would be returned by
    XMLReader, but the parser imposes no constraints on the root
    element so it can be called on small snippets of TTX files.
    """
    # To support snippets with multiple elements, we add a fake root.
    reader = TestXMLReader_()
    reader.parser.Parse("<root>%s</root>" % xmlSnippet, 0)
    return reader.root[2]


class TestXMLReader_(object):
    def __init__(self):
        from xml.parsers.expat import ParserCreate
        self.parser = ParserCreate()
        self.parser.StartElementHandler = self.startElement_
        self.parser.EndElementHandler = self.endElement_
        self.parser.CharacterDataHandler = self.addCharacterData_
        self.root = None
        self.stack = []

    def startElement_(self, name, attrs):
        element = (name, attrs, [])
        if self.stack:
            self.stack[-1][2].append(element)
        else:
            self.root = element
        self.stack.append(element)

    def endElement_(self, name):
        self.stack.pop()

    def addCharacterData_(self, data):
        self.stack[-1][2].append(data)


def getXML(obj, ttFont):
    """Call the object's toXML() method and return the writer's content as string.
    Result is stripped of XML declaration and OS-specific newline characters.
    """
    writer = XMLWriter(BytesIO())
    # don't write OS-specific new lines
    writer.newlinestr = writer.totype('')
    # erase XML declaration
    writer.file.seek(0)
    writer.file.truncate()
    obj.toXML(writer, ttFont)
    xml = writer.file.getvalue().decode("utf-8")
    return xml
