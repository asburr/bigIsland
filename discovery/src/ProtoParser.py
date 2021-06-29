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
#
# https://developers.google.com/protocol-buffers/docs/encoding

# from io import BytesIO
from discovery.src.parser import Parser
from google.protobuf.internal import wire_format, decoder
import struct
import sys
import traceback


class ProtoParser(Parser):
    def __init__(self):
        self.wire_type_defaults = {
            wire_format.WIRETYPE_VARINT: 'int',
            wire_format.WIRETYPE_FIXED32: 'fixed32',
            wire_format.WIRETYPE_FIXED64: 'fixed64',
            wire_format.WIRETYPE_LENGTH_DELIMITED: 'LD',
            wire_format.WIRETYPE_START_GROUP: 'group',
            wire_format.WIRETYPE_END_GROUP: 'endGroup'
        }
        self.wiretypes = {
            'uint': wire_format.WIRETYPE_VARINT,
            'int': wire_format.WIRETYPE_VARINT,
            'sint': wire_format.WIRETYPE_VARINT,
            'fixed32': wire_format.WIRETYPE_FIXED32,
            'sfixed32': wire_format.WIRETYPE_FIXED32,
            'float': wire_format.WIRETYPE_FIXED32,
            'fixed64': wire_format.WIRETYPE_FIXED64,
            'sfixed64': wire_format.WIRETYPE_FIXED64,
            'double': wire_format.WIRETYPE_FIXED64,
            'bytes':  wire_format.WIRETYPE_LENGTH_DELIMITED,
            'str':  wire_format.WIRETYPE_LENGTH_DELIMITED,
            'message':  wire_format.WIRETYPE_LENGTH_DELIMITED,
            'group': wire_format.WIRETYPE_START_GROUP,
            'packed_uint': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_int': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_sint': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_fixed32': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_sfixed32': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_float': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_fixed64': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_sfixed64': wire_format.WIRETYPE_LENGTH_DELIMITED,
            'packed_double': wire_format.WIRETYPE_LENGTH_DELIMITED
        }
        self.decoders = {
            'uint': self.decode_uvarint,
            'int': self.decode_varint,
            'sint': self.decode_svarint,
            'fixed32': self.decode_fixed32,
            'sfixed32': self.decode_sfixed32,
            'float': self.decode_float,
            'fixed64': self.decode_fixed64,
            'sfixed64': self.decode_sfixed64,
            'double': self.decode_double,
            'bytes': self.decode_bytes,
            'str': self.decode_str,
            'packed_uint': self.generate_packed_decoder(self.decode_uvarint),
            'packed_int': self.generate_packed_decoder(self.decode_varint),
            'packed_sint': self.generate_packed_decoder(self.decode_svarint),
            'packed_fixed32': self.generate_packed_decoder(self.decode_fixed32),
            'packed_sfixed32': self.generate_packed_decoder(self.decode_sfixed32),
            'packed_float': self.generate_packed_decoder(self.decode_float),
            'packed_fixed64': self.generate_packed_decoder(self.decode_fixed64),
            'packed_sfixed64': self.generate_packed_decoder(self.decode_sfixed64),
            'packed_double': self.generate_packed_decoder(self.decode_double)
        }
        # Example typedef with descriptions.
        # typedef is constructed or previously defined.
        self.typedef = {
            'type': 'LD or bytes or int or group',
            'name': 'Text name from cfg(manual)',
            'struct': 'Optional dict describing struct for LD(message) and group'
        }
        # Example values
        self.values = {
            'field number or name':
                "[value] or, for struct, {'field': 'values'}"
        }
        self.indent=""

    def parse(self, file: str) -> list:
        j = self.toJSON(file)
        print(j)

    def toJSON(self, file: str) -> dict:
        self.debug = True
        with open(file, "rb") as f:
            self.buf = f.read()
            (self.label, self.pos, self.end,
             self.typedef, self.values, self.group, self.indent) = (
             "", 0, len(self.buf), {}, {}, False, "")
            return self._decode_message()

    def _decode_message(self) -> None:
        if self.debug:
            print(self.indent + "++_decode_message @" + str(self.pos) + 
                  " " + self.label + " len=" + str(self.end-self.pos) +
                  " " + str(self.typedef) + " " + str(self.values))
        messageType = self.typedef
        messageValues = self.values
        messageIndent = self.indent
        self.indent += " "
        while self.pos < self.end:
            oldpos = self.pos
            try:
                fn, wire_type = wire_format.UnpackTag(self._decode_uvarint())
            except Exception as exc:
                raise ValueError(
                       "Could not read valid tag at pos %d. Ensure it is "
                       "a valid protobuf message: %s"
                       % (oldpos, exc))
            field_number = str(fn)
            if field_number not in messageType:
                messageType[field_number] = {
                        'type':self.wire_type_defaults[wire_type]
                }
                messageValues[field_number] = []
            self.typedef = messageType[field_number]
            self.values = messageValues[field_number]
            if self.debug:
                print(self.indent+"+++message field #" + field_number +
                      " @" + str(self.pos) + " " + str(self.typedef) +
                      " " + str(self.values))
            self._decode_message_field(field_number, wire_type)
            if self.debug:
                print(self.indent+"---message field #" + field_number +
                      " @" + str(self.pos) + " " + str(self.typedef) +
                      " " + str(self.values))
        if self.pos > self.end:
            raise decoder._DecodeError(
                "Invalid Message Length, pos=" + str(self.pos) + " end="
                + str(self.end))
        if self.group:
            raise ValueError("Got START_GROUP with no END_GROUP.")
        self.typedef = messageType
        self.values = messageValues
        self.indent = messageIndent
        if self.debug:
            print(self.indent+"--decode_message @" + str(self.pos) + "=" +
                  str(self.typedef) +
                  " " + str(self.values))

    def _decode_message_field(self, field_number: str, wire_type: str) -> None:
        print(self.indent+"_decode_message_field start #" + field_number + " " + str(self.typedef))
        field_type = self.typedef['type']
        if field_type == 'LD':  # Len Delim
            backup = (self.label, self.pos, self.end, self.group, self.indent)
            values = self.values
            self.values = {}
            typedef = self.typedef
            self.typedef = self.typedef.setdefault('message_typedef',{})
            if self.debug:
                print(self.indent + "@"+str(self.pos) + " message "+
                      str(self.typedef))
            self.indent += " "
            try:
                self.decode_lendelim_message()
                typedef['message_typedef'] = self.typedef
                self.typedef = typedef
                values.append(self.values)
                self.values = values
            except Exception:
                traceback.print_exc()
                del typedef['message_typedef']
                (self.label, self.pos, self.end, self.group, self.indent) = backup
                self.values = values
                self.typedef = typedef
                if self.debug:
                    print(self.indent + "@"+str(self.pos) + " Must be bytes!")
                field_type = 'bytes'
                self.decode_bytes()
        elif field_type == "bytes":
            self.decode_bytes()
        elif field_type == 'endGroup':
            if not self.group:
                raise ValueError("Found END_GROUP before START_GROUP")
            self.group = False
        elif field_type == 'group':
            backup = (self.label, self.typedef)
            if 'group_typedef' in typedef:
                self.typedef = typedef['group_typedef']
            else:
                self.typedef = {}
            self.decode_group()
            backup[1]['group_typedef'] = self.typedef
            (self.label, self.typedef) = backup
        else:
            if self.wiretypes[field_type] != wire_type:
                raise ValueError("Invalid wiretype for field number %s. %s "
                                 "is not wiretype %s"
                                 % (field_number, field_type, wire_type))
            self.decoders[field_type]()
        self.typedef['type'] = field_type

    def decode_lendelim_message(self) -> None:
        length = self._decode_varint()
        backup = (self.label, self.end, self.group)
        self.label += ".G" + str(length)
        self.end = self.pos + length
        self.group = False
        self._decode_message()
        (self.label, self.end, self.group) = backup

    def decode_bytes(self) -> None:
        length = self._decode_varint()
        start, self.pos = self.pos, self.pos + length
        self.values.append(self.buf[start:self.pos])
    
    def decode_str(self) -> None:
        self.values.append(
                self.decode_bytes().decode('utf-8', 'backslashreplace'))

    def decode_group(self) -> None:
        backup = (self.group, self.label)
        self.group = True
        self.label += ".group"
        self._decode_message()
        self.group, self.label = backup

    def _decode_uvarint(self) -> int:
        value, self.pos = decoder._DecodeVarint(self.buf, self.pos)
        return value
    
    def decode_uvarint(self) -> None:
        self.values.append(self._decode_uvarint())

    def _decode_varint(self) -> int:
        value, self.pos = decoder._DecodeSignedVarint(self.buf, self.pos)
        return value

    def decode_varint(self) -> None:
        self.values.append(self._decode_varint())
    
    def decode_svarint(self) -> None:
        self.values.append(wire_format.ZigZagDecode(self.decode_uvarint()))

    def _decode_struct(self, fmt) -> None:
        start = self.pos
        self.pos += struct.calcsize(fmt)
        self.values.append(struct.unpack(fmt, self.buf[start:self.pos])[0])
    
    def decode_fixed32(self) -> None:
        self.values.append(self._decode_struct('<I'))
    
    def decode_sfixed32(self) -> None:
        self.values.append(self._decode_struct('<i'))
    
    def decode_float(self) -> None:
        self.values.append(self._decode_struct('<f'))
    
    def decode_fixed64(self) -> None:
        self.values.append(self._decode_struct('<Q'))

    def decode_sfixed64(self) -> None:
        self.values.append(self._decode_struct('<q'))

    def decode_double(self) -> None:
        self.values.append(self._decode_struct('<d'))

    def generate_packed_decoder(self, wrapped_decoder):
        def length_wrapper(self) -> None:
            length = self._decode_varint()
            end = self.pos+length
            output = []
            while self.pos < end:
                output.append(wrapped_decoder())
            if self.pos > end:
                raise decoder._DecodeError("Invalid Packed Field Length")
            self.values.append(output)
        return length_wrapper

    @staticmethod
    def main():
        p = ProtoParser()
        p.parse(file="test.proto")


if __name__ == "__main__":
    ProtoParser.main()

