# https://developers.google.com/protocol-buffers/docs/encoding
from io import BytesIO
from discovery.src.parser import Parser
from google.protobuf.internal import wire_format, encoder, decoder
import struct
import copy
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

    def parse(self, file: str) -> list:
        j = self.toJSON(file)
        print(j)

    def toJSON(self, file: str) -> any:
        self.debug = False
        with open(file, "rb") as f:
            j, td = self.decode_message(f.read())
            return j
    
    def decode_message(self, buf, message_type=None):
        """Decode a message to a Python dictionary.
        Returns tuple of (values, types)
        """
        self.debugStack = 0
        value, typedef, _ = self._decode_message("", buf, message_type)
        return value, typedef

    def _decode_message(self, label: str, buf, typedef=None, pos=0, end=None, group=False):
        """Decode a protobuf message with no length delimiter"""
        print(str(pos) + " decode_message " + label)
        if end is None:
            end = len(buf)

        if typedef is None:
            typedef = {}
        else:
            # Don't want to accidentally modify the original
            typedef = copy.deepcopy(typedef)
        output = {}

        while pos < end:
            oldpos = pos
            tag, pos = decoder._DecodeVarint(buf, pos)
            try:
                field_number, wire_type = wire_format.UnpackTag(tag)
            except Exception as exc:
                raise (ValueError,
                       'Could not read valid tag at pos %d. Ensure it is a valid protobuf message: %s'
                       % (pos-len(tag), exc), sys.exc_info()[2])
            # Convert to str
            field_number = str(field_number)
            orig_field_number = field_number
    
            field_typedef = None
            if field_number in typedef:
                field_typedef = typedef[field_number]
            else:
                field_typedef = {}
                field_typedef['type'] = self.wire_type_defaults[wire_type]
            field_type = field_typedef['type']
            if self.debug:
                ft = field_type
                if ft == None:
                    ft = "None"
                print("@" + str(oldpos) + "-" + str(pos-1) + ":" + label + " field_number " +
                      str(field_number) +
                      " wire_type " + str(wire_type) +
                      " field_type " + str(ft))
            # If field_type is None, its either an unsupported wire type, length delim or group
            # length delim we have to try and decode first
            field_out = None
            if field_type == 'LD':
                field_out, pos = self.decode_message_LD(label, buf, pos, field_typedef)
            elif field_type == 'endGroup':
                # TODO Should probably match the field_number to START_GROUP
                if not group:
                    raise ValueError("Found END_GROUP before START_GROUP")
                # exit out
                return output, typedef, pos
            elif field_type == 'message':
                field_out, pos = self.decode_message_message(
                        label, buf, pos, field_typedef, field_number)
            elif field_type == 'group':
                group_typedef = None
                # Check for a anonymous type
                if 'group_typedef' in field_typedef:
                    group_typedef = field_typedef['group_typedef']
                field_out, group_typedef, pos = self.decode_group(
                        label, buf, group_typedef, pos)
                # Save type definition
                field_typedef['group_typedef'] = group_typedef
            else:
                # Verify wiretype matches
                if self.wiretypes[field_type] != wire_type:
                    raise ValueError("Invalid wiretype for field number %s. %s is not wiretype %s"
                                     % (field_number, field_type, wire_type))
                # Simple type, just look up the decoder
                field_out, pos = self.decoders[field_type](buf, pos)
            field_typedef['type'] = field_type
            if 'name' not in field_typedef:
                field_typedef['name'] = ''
            field_key = field_number
            if '-' not in field_number  and 'name' in field_typedef and field_typedef['name'] != '':
                field_key = field_typedef['name']
            # Deal with repeats
            if field_key in output:
                if isinstance(field_out, list):
                    if isinstance(output[field_number], list):
                        output[field_key] += field_out
                    else:
                        output[field_key] = field_out.append(output[field_key])
                else:
                    if isinstance(output[field_number], list):
                        output[field_key].append(field_out)
                    else:
                        output[field_key] = [output[field_key], field_out]
            else:
                output[field_key] = field_out
                typedef[orig_field_number] = field_typedef
            if self.debug:
                print(str(field_key) + " field_out:" + str(field_out))
        if pos > end:
            raise decoder._DecodeError("Invalid Message Length, pos=" +
                                       str(pos) + " end=" + str(end))
        # Should never hit here as a group
        if group:
            raise ValueError("Got START_GROUP with no END_GROUP.")
        print("decode_message finish " + str(pos))
        return output, typedef, pos

    def decode_message_LD(self, label, buf, pos, field_typedef):
        out, field_type = self.decode_guess(label, buf, pos)
        if field_type == 'message':
            field_out, message_typedef, pos = out
            field_typedef['message_typedef'] = message_typedef
        else:
            field_out, pos = out
        return field_out, pos

    def decode_message_message(self, label, buf, pos, field_typedef, field_number):
        print("##############################")
        message_typedef = None
        # Check for a anonymous type
        if 'message_typedef' in field_typedef:
            message_typedef = field_typedef['message_typedef']
        # Check for type defined by message type name
        elif 'message_type_name' in field_typedef:
            raise Exception("Not implemented")
            # message_typedef = blackboxprotobuf.lib.types.messages[
            #    field_typedef['message_type_name']]
        try:
            field_out, message_typedef, pos = self.decode_lendelim_message(
                label, buf, message_typedef, pos)
            # Save type definition
            field_typedef['message_typedef'] = message_typedef
        except Exception as exc:
            # If this is the root message just fail
            if pos == 0:
                raise exc
        if field_out is None and 'alt_typedefs' in field_typedef:
            # check for an alternative type definition
            for alt_field_number, alt_typedef in field_typedef['alt_typedefs'].items():
                try:
                    field_out, message_typedef, pos = self.decode_lendelim_message(
                        label, buf, alt_typedef, pos)
                except Exception:
                    pass
                if field_out is not None:
                    # Found working typedef
                    field_typedef['alt_typedefs'][alt_field_number] = message_typedef
                    field_number = field_number + "-" + alt_field_number
                    break
        if field_out is None:
            # Still no typedef, try anonymous, and let the error propogate if it fails
            field_out, message_typedef, pos = self.decode_lendelim_message(
                    label, buf, {}, pos)
            if 'alt_typedefs' in field_typedef:
                # get the next higher alt field number
                alt_field_number = str(
                    max(map(int, field_typedef['alt_typedefs'].keys()))
                    + 1)
            else:
                field_typedef['alt_typedefs'] = {}
                alt_field_number = '1'
            field_typedef['alt_typedefs'][alt_field_number] = message_typedef
            field_number = field_number + "-" + alt_field_number
        return field_out, pos

    def decode_guess(self, label, buf, pos):
        """Try to decode as subgroup, then just do as bytes
           Returns the value + the type"""
        try:
            print(str(pos) + " Guess1: trying len delim")
            return self.decode_lendelim_message(label, buf, {}, pos), 'message'
        except Exception:
            print(str(pos) + " Guess2: trying bytes")
            return self.decode_bytes(buf, pos), 'bytes'

    def decode_lendelim_message(self, label: str, buf, typedef=None, pos=0):
        """Read in the length and use it as the end"""
        length, pos = self.decode_varint(buf, pos)
        ret = self._decode_message(label + ".G" + str(length), buf, typedef, pos, pos+length)
        return ret


    def decode_bytes(self, value, pos):
        """Decode varint for length and then the bytes"""
        length, pos = self.decode_varint(value, pos)
        end = pos+length
        return value[pos:end], end
    
    def decode_str(self, value, pos):
        """Decode varint for length and then the string"""
        length, pos = self.decode_varint(value, pos)
        end = pos+length
        return value[pos:end].decode('utf-8', 'backslashreplace'), end

    def decode_group(self, label: str, buf, typedef=None, pos=0, end=None):
        """Decode a protobuf group type"""
        return self._decode_message(label + ".group", buf, typedef, pos, end, group=True)

    def decode_uvarint(self, buf, pos):
        value, pos = decoder._DecodeVarint(buf, pos)
        return (value, pos)
    
    def decode_varint(self, buf, pos):
        value, pos = decoder._DecodeSignedVarint(buf, pos)
        return (value, pos)
    
    def decode_svarint(self, buf, pos):
        output, pos = self.decode_uvarint(buf, pos)
        return wire_format.ZigZagDecode(output), pos

    def decode_struct(self, fmt, buf, pos):
        """Generic method for decoding arbitrary python "struct" values"""
        new_pos = pos + struct.calcsize(fmt)
        return struct.unpack(fmt, buf[pos:new_pos])[0], new_pos
    
    _fixed32_fmt = '<I'
    def decode_fixed32(self, buf, pos):
        """Decode a single 32 bit fixed-size value"""
        return self.decode_struct(self._fixed32_fmt, buf, pos)
    
    _sfixed32_fmt = '<i'
    def decode_sfixed32(self, buf, pos):
        """Decode a single signed 32 bit fixed-size value"""
        return self.decode_struct(self._sfixed32_fmt, buf, pos)
    
    _float_fmt = '<f'
    def decode_float(self, buf, pos):
        """Decode a single 32 bit floating point value"""
        return self.decode_struct(self._float_fmt, buf, pos)
    
    _fixed64_fmt = '<Q'
    def decode_fixed64(self, buf, pos):
        """Decode a single 64 bit fixed-size value"""
        return self.decode_struct(self._fixed64_fmt, buf, pos)
    
    _sfixed64_fmt = '<q'
    def decode_sfixed64(self, buf, pos):
        """Decode a single signed 64 bit fixed-size value"""
        return self.decode_struct(self._sfixed64_fmt, buf, pos)
    
    _double_fmt = '<d'
    def decode_double(self, buf, pos):
        """Decode a single 64 bit floating point value"""
        return self.decode_struct(self._double_fmt, buf, pos)

    def generate_packed_decoder(self, wrapped_decoder):
        """Generate an decoder for a packer type from a base type decoder"""
        def length_wrapper(buf, pos):
            """Decode repeat values prefixed with the length"""
            length, pos = self.decode_varint(buf, pos)
            end = pos+length
            output = []
            while pos < end:
                value, pos = wrapped_decoder(buf, pos)
                output.append(value)
            if pos > end:
                raise decoder._DecodeError("Invalid Packed Field Length")
            return output, pos
        return length_wrapper

    @staticmethod
    def main():
        p = ProtoParser()
        p.parse(file="test.proto")
        # p.parse(file="dataset.google_message2.pb")


if __name__ == "__main__":
    ProtoParser.main()

