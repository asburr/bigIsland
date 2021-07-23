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

# Id the type from a string.
# Catastrophic Backtracking in regex:
#
# Complicated expressions are avoided to reduce the possibility of catastrophic backtracking
# [http://www.regular-expressions.info/catastrophic.html]. This is somewhat obvious in a simple expression, for
# example, the pattern "(\w+)\*([\w\s]+)*/$" has a mistake in the second capture group, "([\w\s]+)*" should be
# "([\w\s]+)", and the nested qualifiers of "*" and "*" causes catastrophic backtracking. The nested qualifiers
# has the expression trying all permutations of the string and with very long strings these permutations will take
# days to compute.
#
# Example of catastrophic backtracking,
# python3 -mtimeit -n 1 -r 1 -s'import re' 'p = re.compile("(\w+)\*([\w\s]+)*/$")' 'm = p.match("1*12345678910")'
# 1 loops, best of 1: 324 usec per loop
# Example of catastrophic backtracking with a longer string to show the matching gets slower due to backtracking,
# python3 -mtimeit -n 1 -r 1 -s'import re' 'p = re.compile("(\w+)\*([\w\s]+)*/$")' 'm = p.match("1*1234567891012345678912345")'
# 1 loops, best of 1: 1.78 sec per loop
# Example without catastrophic backtracking with the long string to show performance without backtracking,
# python3 -mtimeit -n 1 -r 1 -s'import re' 'p = re.compile("(\w+)\*([\w\s]+)/$")' 'm = p.match("1*1234567891012345678912345")'
# 1 loops, best of 1: 221 usec per loop
#
import ipaddress
# from ipaddress import IPv4Address
# import uuid
import re
from magpie.src.mzdatetime import MZdatetime


class MIsType:
    # The only valid characters for a domain name are letters, numbers and a hyphen "-".
    dmPat = re.compile("^(?!-)(([A-Z0-9-]|\\[0-9][0-9]){1,63}[.]?(?<!-))+$", re.IGNORECASE)

    @classmethod
    def isDomain(cls, label: str, json_type: type, value: str) -> (str, dict):
        if json_type != str:
            return ("",{})
        label_good = False
        for lbl in ["dom", "host", "source"]:
            label_good |= (lbl in label)
        if not label_good:
            return ("",{})
        if len(value) > 253:
            return ("",{})
        if cls.dmPat.match(value):
            return ("domain",{})
        return ("",{})

    @staticmethod
    def testDomain():
        for test in [
            (MIsType.isDomain, "domain", str, "bigstuff.cornell.edu1", "domain"),
            (MIsType.isDomain, "host", str, "street-map.uk.co", "domain"),
            (MIsType.isDomain, "domain", str, "bigstuff.cornell.edu ", ""),
            (MIsType.isDomain, "host", str, "street-map?uk.co", "")
        ]:
            yield test

    # Amazon Resource Name
    # arn:partition:service:region:account-id:resource-id
    # arn:partition:service:region:account-id:resource-type/resource-id
    # arn:partition:service:region:account-id:resource-type:resource-id
    ARNPat = re.compile(
        # Starts with arn
        "^arn:"
        # partition
        "([^:\s]*):"
        # service
        "([^:\s]*):"
        # region
        "([^:\s]*):"
        # account-id
        "([^:\s]*):"
        # resouce-type is optional
        "(?:([^:/\s]*)[:/])?"
        # Resource id
        "([^:\s]+)$"
        ,
        re.IGNORECASE
    )

    @classmethod
    def isARN(cls, label: str, json_type: type, value: str) -> (str,dict):
        if json_type != str:
            return ("",{})        
        if cls.ARNPat.match(value):
            return ("arn", {})
        return ("",{})

    @staticmethod
    def testARN():
        for test in [
            (MIsType.isARN, "arn", str, "arn:aws:iam::123456789012:user", "arn"),
            (MIsType.isARN, "arn", str, "arn:aws:iam::123456789012:user/Development/product_1234/*", "arn"),
            (MIsType.isARN, "arn", str, "arm:abc", ""),
            (MIsType.isARN, "arn", str, "arn:abc:abc:abc abc", "")
        ]:
            yield test

    # User Agent.
    # product/version (system and browser information) {repeated}
    UAPat = re.compile(
        "^"
        # Product
        "[^\s/()]+\s?"
        # version
        "/\s?[\da-z-_.]+"
        # (system and browser information) is optional
        "(?:\s[(][^)]+[)]\s?)?"
        # Additional products
        "(?:"
        "\s[^\s/()]+\s?"
        # additional products have optional version
        "(?:/\s?[\da-z-_.]+)?"
        # (system and browser information) is optional
        "(?:\s[(][^)]+[)]\s?)?"
        ")*"
        "$",
        re.IGNORECASE)

    @classmethod
    def isUA(cls, label: str, json_type: type, value: str) -> (str, dict):
        if json_type != str:
            return ("",{})
        if cls.UAPat.match(value):
            return ("ua", {})
        return ("",{})

    @staticmethod
    def testUA():
        for test in [
            (MIsType.isUA, "", str, "Mozilla/5.0 (Linux; Android 8.0.0; SM-G960F Build/R16NW)", "ua"),
            (MIsType.isUA, "", str, "AppleWebKit/604.1.34 (KHTML, like Gecko)", "ua"),
            (MIsType.isUA, "", str, "Version/11.0 Mobile/15A5341f Safari/604.1", "ua"),
            (MIsType.isUA, "", str, "Chrome/46.0.2486.0 Mobile Safari/537.36", "ua")
        ]:
            yield test

    # Email: userid@(domain|ip)
    emailPat = re.compile(
        # user id
        # starts with [a-z0-9] and [_.-] must be followed by one or more [a-z0-9].
        "^([A-Z0-9](?:[_.-][A-Z0-9]|[A-Z0-9])*)@"
        # Domain or ip
        "(.*)$",
        re.IGNORECASE)

    @classmethod
    def isEmail(cls, label: str, json_type: type, value: str) -> (str, dict):
        if json_type != str:
            return ("",{})
        m = cls.emailPat.match(value)
        if m:
            domain = m.groups()[1]
            if cls.isDomain("domain", str, domain):
                return ("email", {})
            if cls.isIP("ip", str, domain) == "ip:global":
                return ("email", {})
        return ("",{})

    @staticmethod
    def testEmail():
        for test in [
            (MIsType.isEmail, "", str, "abc-d@mail.com", "email"),
            (MIsType.isEmail, "", str, "abc.def@mail.com", "email"),
            (MIsType.isEmail, "", str, "abc_def@mail.com", "email"),
            (MIsType.isEmail, "", str, "abc_def@1.2.3.4", "email"),
            (MIsType.isEmail, "", str, "abc-@mail.com", ""),
            (MIsType.isEmail, "", str, "abc..def@mail.com", ""),
            (MIsType.isEmail, "", str, ".abc@mail.com", ""),
            (MIsType.isEmail, "", str, "abc#def@mail.com", "")
        ]:
            yield test

    # IPaddress
    @classmethod
    def isIP(cls, _label: str, json_type: type, value: str) -> (str,dict):
        if json_type != str:
            return ("",{})
        if value.count(".") == 3 or value.count(":") > 1:
            try:
                ip = ipaddress.ip_address(value)
                iptype = "ip"
                # The IP version should not matter.
                #  if isinstance(ip, IPv4Address):
                #     iptype += ":v4"
                # else:
                #     iptype += ":v6"
                if ip.is_multicast:
                    iptype += ":multicast"
                elif ip.is_private:
                    iptype += ":private"
                elif ip.is_global:
                    iptype += ":global"
                elif ip.is_unspecified:
                    iptype += ":unspecified"
                elif ip.is_reserved:
                    iptype += ":reserved"
                elif ip.is_link_local:
                    iptype += ":link_local"
                return (iptype, {})
            except Exception:
                pass
        return ("",{})

    @staticmethod
    def testIP():
        for test in [
            (MIsType.isIP, "", str, "1.2.3.4", "ip:global"),
            (MIsType.isIP, "", str, "12::13", "ip:global"),
            (MIsType.isIP, "", str, "af::af", "ip:global"),
            (MIsType.isIP, "", str, "1.2.3", ""),
            (MIsType.isIP, "", str, "a.f.g.f", ""),
            (MIsType.isIP, "", str, "123af::12af", ""),
            (MIsType.isIP, "", str, "123:", "")
        ]:
            yield test

    @classmethod
    def isTimestamp(cls, label: str, json_type: type, value: str) -> (str, dict):
        if "time" in label:
            if json_type == str:
                try:
                    float(value)
                    try:
                        int(value)
                        return ("timestamp:epoch(int)",{})
                    except Exception:
                        return ("timestamp:epoch(float)",{})
                except Exception:
                    return ""
            if json_type == float:
                return ("timestamp:epoch(float)",{})
            if json_type == int:
                return ("timestamp:epoch(int)",{})
        if json_type != str:
            return ("",{})
        try:
            MZdatetime.strptime(value)
            return ("timestamp",{})
        except Exception:
            return ("",{})

    @staticmethod
    def testTimestamp():
        for test in [
            (MIsType.isTimestamp, "time", int, "1234", "timestamp:epoch(int)"),
            (MIsType.isTimestamp, "time", float, "1234.5", "timestamp:epoch(float)"),
            (MIsType.isTimestamp, "", str, "2012-12-12T10:53:43", "timestamp"),
            (MIsType.isTimestamp, "", str, "2012-14-12T10:53:43", "")
        ]:
            yield test

    # URI: <schema>:<userinfo>[:<password>]@<host>[:<port>][;<uri-parameters>][?<headers>]
    URIPat = re.compile(
        # Notes on the regex syntax:
        # (?:...) non-capture group.
        # ()? optional group.
        # Protocol.
        "^([a-z]{3,}):"
        # userinfo
        "([^@^:]+)"
        # password
        "(?::([^@]+))?@"
        # Domain or ip
        "([^:^;]{4,})"
        # port
        "(?::([0-9]+))?"
        # params and headers
        "(?:[;?](.*))?$",
        re.IGNORECASE)

    @classmethod
    def isURI(cls, label: str, json_type: type, value: str) -> (str, dict):
        if json_type != str:
            return ("",{})
        m = cls.URIPat.match(value)
        if not m:
            return ("",{})
        ret = {}
        (ret["protocol"], ret["userinfo"], ret["password"],
         ret["domain"], ret["port"],
         ret["params"]) = m.groups()
        if not cls.isDomain("host", str, ret["domain"]):
            if not cls.isIP("", str, ret["domain"]):
                return ("",{})
            ret["ip"] = ret["domain"]
            del ret["domain"]
        return ("uri",ret)

    @staticmethod
    def testURI():
        for test in [
            (MIsType.isURI, "", str, "sip:1-999-123-4567@voip-provider.example.net", "uri"),
            (MIsType.isURI, "", str, "1-999-123-4567@voip-provider.example.net", ""),
            (MIsType.isURI, "", str, "sips:1-999-123-4567@voip-provider.example.net", "uri"),
            (MIsType.isURI, "", str, "sip:1-999-123-4567:password@voip-provider.example.net;params", "uri"),
            (MIsType.isURI, "", str, "1-999-123-4567:password192.168.0.1", "")
        ]:
            yield test

    # URL: protocol://(domain|IPAddress):port/path(#anchor|?param)
    # param: (key=value)key2=value2
    URLPat = re.compile(
        # Notes on the regex syntax:
        # (?:...) non-capture group.
        # ()? optional group.
        # Protocol.
        "^(?:([a-z]{3,}):)?//"
        # Domain or ip
        "([^/]{4,})"
        # port
        "(?::([0-9]+))?"
        # path
        # note: added not "(" and not space (\s) to avoid matching UA.
        # note: added optional path.
        "(/([^\s(#?]+))?"
        # "(/([^#?]+))"
        # parameter, one capture for all params
        "((?:[?][^?#]+)*)?"
        # anchor, one capture for all anchors.
        "((?:#[^?#]+)*)?$",
        re.IGNORECASE)

    @classmethod
    def isURL(cls, label: str, json_type: type, value: str) -> (str,dict):
        if json_type != str:
            return ("",{})
        m = cls.URLPat.match(value)
        if not m:
            return ("",{})
        ret = {}
        (ret["protocol"], ret["domain"], ret["port"],
         ret["path"], ret["params"], ret["anchor"],
         ret["other"]) = m.groups()
        if cls.isDomain("host", str, ret["domain"]):
            if (ret["port"] is None and ret["path"] is None and
                ret["params"] is None):
                if "." not in ret["domain"]:
                    return ("",{})
        else:
            if cls.isIP("", str, ret["domain"]):
                ret["ip"] = ret["domain"]
                del ret["domain"]
            else:
                return ("",{})
        return ("url",ret)

    @staticmethod
    def testURL():
        for test in [
            (MIsType.isURL, "", str, "http://www.landofcode.com/html/url-format.php", "url"),
            (MIsType.isURL, "", str, "http://www.landofcode.com/html/html-basics.php", "url"),
            (MIsType.isURL, "", str, "https://www.amazon.com", "url"),
            (MIsType.isURL, "", str, "ftp://www.somesite.com/ftp/file.exe", "url")
        ]:
            yield test

    @classmethod
    def isBool(cls, label: str, json_type: type, value: str) -> (str,dict):
        if json_type == "bool":
            return ("bool",{})
        if json_type != str:
            return ("",{})
        if value in ["True", "true", "False", "false"]:
            return ("bool",{})
        return ("",{})

    @staticmethod
    def testBool():
        for test in [
            (MIsType.isBool, "", str, "True", "bool")
        ]:
            yield test

    MACPat = re.compile(
        # Colon-Hexadecimal notation is used by Linux OS.
        # Period-separated Hexadecimal notation is used by Cisco Systems
        # Organizational Unique Identifier (Manufacturer)
        "^([0-9A-F]{2}[:-][0-9A-F]{2}[:-][0-9A-F]{2})[:-]"
        # Network Interface Controller
        "([0-9A-F]{2}[:-][0-9A-F]{2}[:-][0-9A-F]{2})$",
        re.IGNORECASE)

    MACPat2 = re.compile(
        # Organizational Unique Identifier (Manufacturer)
        "^([0-9A-F]{4}[-.][0-9A-F]{4}[-.])"
        # Network Interface Controller
        "([0-9A-F]{4}[-.][0-9A-F]{4})$",
        re.IGNORECASE)

    @classmethod
    def isMAC(cls, label: str, json_type: type, value: str) -> (str,dict):
        if json_type != str:
            return ("",{})
        if cls.MACPat.match(value) or cls.MACPat2.match(value):
            return ("mac",{})
        return ("",{})

    @staticmethod
    def testMAC():
        for test in [
            (MIsType.isMAC, "", str, "00:25:96:FF:FE:12", "mac"),
            (MIsType.isMAC, "", str, "0025-96FF-FE12-3456", "mac"),
            (MIsType.isMAC, "", str, "00 1B 77 49 54 FD", "")
        ]:
            yield test

    # UUID LLLL-M-M-H-HRLDDDDD
    # 0-3: L time_low, The low field of the timestamp
    # 4-5: M time_mid, The middle field of the timestamp
    # 6-7: H time_hi_and_version, The high field of the timestamp multiplexed with the version number
    # 8-8: R clock_seq_hi_and_reserved, The high field of the clock sequence multiplexed with the variant
    # Variant:
    # Msb0  Msb1  Msb2    Description
    #  0     x     x    0 Reserved, NCS backward compatibility.
    UUIDvariant0OR = int("1000", 2)
    UUIDvariant0 = int("0000", 2)
    #  1     0     x    2 The variant specified in this document.
    UUIDvariant2OR = int("1100", 2)
    UUIDvariant2 = int("1000", 2)
    #  1     1     0    6 Reserved, Microsoft Corporation backward compatibility
    UUIDvariantXOR = int("1110", 2)
    UUIDvariant6 = int("1100", 2)
    #  1     1     1    7 Reserved for future definition.
    UUIDvariant7 = int("1110", 2)
    # 9-9: L clock_seq_low, The low field of the bit integer clock sequence
    # 10:15: D node, The spatially unique node identifier
    UUIDPat = re.compile(
        "^[0-9A-F]{8}-[0-9A-F]{4}-([0-9A-f])[0-9A-F]{3}-([0-9A-Z])[0-9A-F]{3}-[0-9A-F]{12}$",
        re.IGNORECASE)

    @classmethod
    def isUUID(cls, label: str, json_type: type, value: str) -> (str,dict):
        if json_type != str:
            return ("",{})
        m = cls.UUIDPat.match(value)
        variant = "?"
        if m:
            N = int(m.groups()[1], 16)
            if N & cls.UUIDvariant0OR == cls.UUIDvariant0:
                variant = "0"
            elif N & cls.UUIDvariant2OR == cls.UUIDvariant2:
                variant = "2." + str(int(m.groups()[0], 16))
            else:
                n = N & cls.UUIDvariantXOR
                if n == cls.UUIDvariant6:
                    variant = "6"
                elif n == cls.UUIDvariant7:
                    variant = "7"
            return ("uuid:v" + str(variant), {})
        return ("",{})

    @staticmethod
    def testUUID():
        for test in [
            (MIsType.isUUID, "", str, "123e4567-e89b-12d3-a456-426614174000", "uuid:v2.1"),
            (MIsType.isUUID, "", str, "00112233-4455-6677-8899-aabbccddeeff", "uuid:v2.6"),
            (MIsType.isUUID, "", str, "00000000-0000-0000-0000-000000000000", "uuid:v0"),
            (MIsType.isUUID, "", str, "4c0f11c0-897f-11eb-ba78-9b1d7b3ae663", "uuid:v2.1"),
            (MIsType.isUUID, "", str, "9fe3ae99-cfa2-2889-be5a-a931b309b5df", "uuid:v2.2"),
            (MIsType.isUUID, "", str, "4c0f11c0-897f-31eb-ba78-9b1d7b3ae663", "uuid:v2.3"),
            (MIsType.isUUID, "", str, "25A8FC2A-98F2-4B86-98F6-84324AF28611", "uuid:v2.4"),
            (MIsType.isUUID, "", str, "72bc9298-787b-582a-86ac-1141062ba2ed", "uuid:v2.5"),

        ]:
            yield test

    @classmethod
    def isASN(cls, label: str, json_type: type, value: str) -> (str, dict):
        if value.isdigit() and label in ["asn", "autonomous system number"]:
            return ("asn",{})
        return ("",{})

    @staticmethod
    def testASN():
        for test in [
            (MIsType.isASN, "asn", str, "401309", "asn"),
        ]:
            yield test

    @classmethod
    def isType(cls, label: str, json_type: type, value: str) -> (str,dict):
        for i in [
            MIsType.isIP, MIsType.isTimestamp, MIsType.isUUID, MIsType.isMAC, MIsType.isEmail, MIsType.isBool,
            MIsType.isDomain, MIsType.isURL, MIsType.isARN,
            MIsType.isUA, MIsType.isASN
        ]:
            t = i(label, json_type, value)
            if t:
                return (t,{})
        return ("",{})

    @staticmethod
    def getTestCases():
        yield from MIsType.testIP()
        yield from MIsType.testBool()
        yield from MIsType.testTimestamp()
        yield from MIsType.testUUID()
        yield from MIsType.testARN()
        yield from MIsType.testUA()
        yield from MIsType.testEmail()
        yield from MIsType.testURL()
        yield from MIsType.testDomain()
        yield from MIsType.testASN()
        yield from MIsType.testMAC()
        yield from MIsType.testURI()

    @classmethod
    def getMainType(cls, t: str) -> str:
        if ":" in t:
            return t[:t.index(":")]
        return t

    @classmethod
    def isSame(cls, t1: str, t2: str) -> bool:
        t = ["url", "domain", "ip"]
        return cls.getMainType(t1) in t and cls.getMainType(t2) in t

    @staticmethod
    def main():
        pf = None
        for test in MIsType.getTestCases():
            f, l, t, s, r = test
            if f != pf:  # New function, test other func cases against this function.
                for test in MIsType.getTestCases():
                    of, ol, ot, os, o_r = test
                    if of == f:
                        continue
                    g,d = f(ol, ot, os)
                    g2,d2 = of(ol, ot, os)
                    if g and o_r and not MIsType.isSame(g, g2):
                        print("Conflict " + f.__name__ + " returned " + str(g) +
                              " " + str(d) +
                              " which comflicts with " + str(o_r) + "/" +
                              of.__name__ + " returned " + str(g2) + " " + str(d2) +
                              " from value, \"" + str(os) + "\"")
            pf = f
            g,d = f(l, t, s)
            if g != r:
                print("Failed " + str(s) + " got " + str(g) + " exp " + str(r) + " l=" + l + " t=" + str(t))


if __name__ == "__main__":
    MIsType.main()
