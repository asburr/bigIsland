# JSONParser

JSON is the common language outputted by other parsers.

# Stats

Stats for fields seen are occurrence(c), example(e), datatype(dt), and
values(v) with counts.

Stats has software procedures to identify the datatype of each value. Fields
may hold more than one type of data. Each type is tracked with an occurrence
and an example.

Monitoring of Field values is activated by the --values option, through a
file lilsting the Field names whose values are tracked in the stats(v).

Example,
```sh
{
    '->item->Queries->item->dns.qry.name': {
        'c': 3,
        'e': 'bolt.dropbox.com',
        'dt': {
            'url': {
                'c': 3,
                'e': 'bolt.dropbox.com'
            }
        },
        'v': {
            'bolt.dropbox.com': {
                'c': 1
            },
            'bolt.dropbox2.com': {
                'c': 2
            }
        }
    }
}
```

# Options

Optional functionality provides general purpose features to transform JSON. 
These options originate from the need to clean Wireshark's output.

## values

File containing a list of fields. Stats tracks all of the values for these fields.
See above stats.
 
## valuelabels

Option valuelabels provides a file containing a JSON list of either
* blocklabel, keylabel, replacelabel;
* or, blocklabel, keylabel

### blocklabel, keylabel, replacelabel

Replaces the keylabel with the value in replacelabel.
Example is the JSON dissector. JSON is reported in tshark using the following
structure. The labels are generic with names like json.member and json.key
whereas the real labels are found in the value that is labelled as “json.key”.

Example wireshark output requiring valuelabels,
```sh
[
    {
        “json”: {
            “json.object”: {
                “json.member”: {
                    “json.object”: {
                        “json.member”: {
                            “json.value.string”: “12345”,
                            “json.key”: “v1”
                        },
                        “json.member”: {
                            “json.value.number”: 123,
                            “json.key”: “v2”
                        }
                    },
                    “json.key”: “record”
                }
            }
        }
    }
]
```

Using the line "json,json.key,json.member”. Which says, within the nested
structure of tag “json”, replace the tag json.member with the value in the
nested tag json.key.

Example transformed wireshark output by valuelabels,
```sh
[
    {
        “json”: {
            “json.object”: {
                “record”: {
                    “json.object”: {
                        “v1”: {
                            “json.value.string”: “12345”,
                            “json.key”: “v1”
                        },
                        “v2”: {
                            “json.value.number”: 123,
                            “json.key”: “v2”
                        }
                    },
                    “json.key”: “record”
                }
            }
        }
    }
]
```

### blocklabel, keylabel

Insert tag from nest tag’s value. Protocols encode the message type nested
within the field of the message. Tshark reports the value of the message
type but what we need are the other fields of the message to be reported
within the context of this message type. 

blocklabel identifies the message. keylabel identifies the message type.

Example actual options,
```sh
http,urlencoded_form.key
xml,xml.tag
http,http.request
http,http.response_code 
```

Demonstration,
```
[{
    “protocol”: {
        “length”: 123,
        “protocol.msg.code”: "ping”,
        “protocol.param”: {
            “protocol.param.code”: “pong”,
            “protocol.param.flags”: “0x12”
        }
    }
}] 

options,
protocol, protocol.msg.code
protocol.param, protocol.param.code

[{
    “protocol”: {
        "ping": {
            “length”: 123,
            “protocol.msg.code”: "ping”,
            “protocol.param”: {
                "pong": {
                    “protocol.param.code”: “pong”,
                    “protocol.param.flags”: “0x12”
                }
            }
        }
    }
}] 
```

## nest

Option nest provides a file containing a JSON list of fields.

Wireshark reports nested protocols as fields in a dictionary.
For example,
```sh
{
    "_source": {
        "layers": {
            "frame": {
                "frame.interface_id": "0"
            },
            "eth": {
                "eth.dst": "3c:77:e6:18:f7:6d"
            },
            "ip": {
                "ip.version": "4"
            }
        }
    }
}
```
The option, "layers", adds nexting to the layers. For example,
```sh
{
    "_source": {
        "frame": {
            "frame.interface_id": "0",
            "eth": {
                "eth.dst": "3c:77:e6:18:f7:6d",
                "ip": {
                    "ip.version": "4"
                }
            }
        }
    }
}
```

## ignore

Option ignore provides a file containing a JSON list of fields.

Wireshark fields Random content in sub field labels of data-text-lines. There
is an object called data-text-lines, the members have labels that are data from
the file.

Example superfulious fields that need ignoring,
```sh
[
    {
        “http”: {
            “http.request”: “1”,
            “http.request_number”: “1”,
            “http.file_data”: “123
456
789”,
            “data-text-lines”: {
                “123”: “”,
                “456”: “”,
                “789”: “”
            }
        }
    }
]
```

Adding field data_text_lines will ignore that hierarchy.

Example output using ignore,
```sh
[
    {
        “http”: {
            “http.request”: “1”,
            “http.request_number”: “1”,
            “http.file_data”: “123
456
789”
        }
    }
]
```

## valueprune

wireshark x509 is reported in one layer but is reported many times in
frame.protocols, for example, eth:ethertype:ip:tcp:ssl:x509sat:x509sat.

This option prunes the value. format is field, 
