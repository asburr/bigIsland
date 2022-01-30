# Sheet
The expression, three sheets to the wind, describes a sailing boat being tossed around in heavy seas using all three sails, the jib included, in an attempt to maintain the course. It also describes an inebriated person who is trying to maintain control but is in danger of upending and falling over.

Sheet is used to create analytics from a sample of documents (JSON Files), and then to deploy the analytic. A deployed analytic run continuously to process a stream of documents in the processing environment called Hallelujah. Sheet has one grid that displays the sample documents. Each document is a row in the grid, each field of the document is a column in the grid.

Sheet uses Discovery to flatten the documents, and to have a list of the fields seen across the sample documents.

1. <a href="sheet/wi.py">wx Gui</a> Desktop client for the Hallelujah database;
2. <a href="sheet/QueryParams.py">QueryParams</a> helper class for building forms for wi.py;
3. <a href="sheet/Grid.py">grid</a> Helper class for building a grid for wi.py.

