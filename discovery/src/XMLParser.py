# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# See the GNU General Public License, <https://www.gnu.org/licenses/>.
import xml.etree.ElementTree as ET
from discovery.src.parser import Parser
import xml.sax


class XMLHandler(xml.sax.handler.ContentHandler):
    def __init__(self):
        self.attrs = None
        self.chars = ""
        self.start = None
        self.stack = []
        self.record = {}
        self.records = []
        self.endRecord = None

    def parse(self, f):
        xml.sax.parse(f, self)
        return self._result

    def characters(self, data):
        self.chars += data

    def startElement(self, name, attrs):
        if self.start is not None:
            # Nested element.
            parent = self.record
            parent[self.start] = self.record = {}
            self.stack.append(parent)
        self.start = name
        if attrs.getLength():
            self.attrs = {}
            for attname in attrs.getNames():
                self.attrs[attname] = attrs.getValue(attname)

    def endElement(self, name):
        if self.start != name:
            # end of nested element
            self.record = self.stack.pop()
        if len(self.chars.strip()) == 0:
            self.chars = None
        if self.attrs:
            value = {"attrs": self.attrs}
            if self.chars:
                value["value"] = self.chars
            self.attrs = None
        else:
            value = self.chars
        self.chars = ""
        if name not in self.record:
            self.record[name] = value
        else:
            if not isinstance(self.record[name],list):
                self.record[name] = [self.record[name]]
            self.record[name].append(value)
        if name == self.endRecord:
            self.records.append(self.record)
        elif len(self.stack):
            self.records.append(self.record)


class XMLParser(Parser):
    """Detect XSD.
Assumes the children are sequenced. A duplicate tag in the sequence
is converted to a list. A duplicate tag not in sequence is renamed 
by appending a tag counter .
For example, field(test) is seen twice but not in sequence i.e.
field(ab) is in between, and field(test) is not a list.
    <tests><test>123</test><ab>12</ab><test>789</test></tests>
    {'tests': {'test': {'_val_': '123'}, 'ab': {'_val_': '12'},
               'test2': {'_val_': '789'}}}
example, field(test) is seen twice and is in sequence i.e. field(test)
is after field(test), and field(test) is a list.
    <tests><test>123</test><test>789</test></tests>
    {'tests': {'test': [{'_val_': '123'}, {'_val_': '789'}]}}
example, field(test) is seen three times, and the second time is a list.
    <tests><test>123</test><ab>12</ab><test>456</test><test>789</test></tests>
    {'tests': {'test': {'_val_': '123'}, 'ab': {'_val_': '12'},
               'test2': [{'_val_': '456'}, {'_val_': '789'}]}}
    """
    def parse(self, file: str) -> list:
        j = self.toJSON({"filename": file})
        print(j)

    def toJSON(self, param: dict) -> any:
        with open(param["filename"], newline='') as file:
            param["file"] = file
            yield self.toJSON_FD(param)
        
    def toJSON_FD(self, param: dict) -> any:
        offset = param["offset"]
        self.parser = xml.sax.make_parser()
        self.parser.setFeature(xml.sax.handler.feature_namespaces, 0)
        handler = XMLHandler()
        recordCount = 0
        for line in param["file"].readline():
            self.parser.feed(line, handler)
        for record in handler.records:
            recordCount += 1
            if recordCount >= offset:
                yield record
        handler.records = []

    def toJSON_old(self, file: str) -> any:
        root = ET.parse(file).getroot()
        return {root.tag: self._toJSON_old(root)}
    
    def _toJSON_old(self, root: ET.Element) -> any:
        tagcnt = {}
        j = {}
        if len(root.attrib):
            for k, v in root.attrib.items():
                j.setdefault("_att_",{})[k] = v
        children = list(root)
        if len(children):
            lasttag = ""
            for child in children:
                tag = child.tag
                if tag == lasttag:  # list
                    if tagcnt[tag] > 1:
                        tag = child.tag + str(tagcnt[tag])
                    v = j[tag]
                    if isinstance(v,list):
                        v.append(self._toJSON(child))
                    else:
                        j[tag] = [v, self._toJSON(child)]
                else:
                    if tag in j:  # duplicate field
                        tagcnt[tag] += 1
                        tag = child.tag + str(tagcnt[tag])                        
                    j[tag] = self._toJSON(child)
                tagcnt[tag] = 1
                lasttag = child.tag
            return j
        v = root.text
        if not v.strip():
            v = None
        if j:
            j["_val_"] = v
            return j
        return v

    @staticmethod
    def main():
        p = XMLParser()
        p.parse(file="test.xml")


if __name__ == "__main__":
    XMLParser.main()