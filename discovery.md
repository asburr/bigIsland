# Discovery
Willem Janszoon was the first European to discovered Australia. Prior to that discovery, people from Asia has discovered Australia.

Discovery is fed a sample of documents (JSON object) that originate from the same source. The document may look different but discovery finds the common aspects. Discovery outputs a list of all of the fields seen in the documents. More samples may be fed into Discovery along with the prior Discovered fields, and Discovery will update the reported fields and report the differences for example, new fields that have not been seen before, and old fields that were once seen but not recently and assumed to be obsolete.

The output of Discovery (the list of fields) is used by the analytic building tool (called Sheet) which aids users to build (and deploy) analytics to the stream processing tool (called Hallelujah).

1. <a href="discovery/src/parser.py">parser</a> Base class for a parser;
2. <a href="discovery/src/CSVParser.py">CSV parser</a>;
3. <a href="discovery/src/JSONParser.py">JSON parser</a>;
4. <a href="discovery/src/JSONParser.md">JSON parser doc</a> some JSON formats need fixing, for example, wireshark output;
5. <a href="discovery/src/ProtoParser.py">Google's protobuf parser</a>;
6. <a href="discovery/src/XMLParser.py">XML parser</a>;
7. <a href="discovery/src/discovery.py">Discovery</a> builds a schema from the data;
