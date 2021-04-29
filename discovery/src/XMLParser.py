import xml.etree.ElementTree as ET
from discovery.src.parser import Parser


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
        j = self.toJSON(file)
        print(j)

    def toJSON(self, file: str) -> any:
        root = ET.parse(file).getroot()
        return {root.tag: self._toJSON(root)}
    
    def _toJSON(self, root: ET.Element) -> any:
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