# Hallelujah

This project is a software application for data processing, for the a Unix
computer platform. It automatically scales to use all available processing
on a single computer, and continues to scale across multiple computers.
Scaling occurs automatically, in response to a change in congestion levels.

Access to the database is gained through applications that contain the
Hallelujah Python package. This package manages the communication with the
database. There is a minimalistic user interface called Window Interface
(module wi), it is found in the Database's sheets package. It can be used
to explore and update the database.

The database has the following components.
 * Congregation - represents the Unix host;
 * Hallelu - represents the analytic, controls the creation of Jah;
 * Jah - a unit of data processing with six flavours:
     input: either streaming or periodic ingest.
       ** data stream
       ** data ingest
     processing: may transform a datastream and/or join two datastreams.
       ** Transform - transform data;
       ** Join - join two datastreams, produces an enriched datastream.
     routing: selects a datastream by director and/or manager.
       ** Director - route on partition key;
       ** Manager - route on uptime key.
 * Datastream - a data conduit, a connection between Jahs.

Redundancy is provided by three congregations running on different hosts.
The cluster ensures that an analytic on a failed host restarts on another.

The Hallelujah package communicates with any one of the congregations.

Data Processing is managed as a Tradecraft. A tradecraft is captured in a json
document which is not easy to manually edit. Therefore, Tradecraft are built
using applications that provide a user friendly way to create the tradecraft.
Applications send the json document to the database and that creates the
Tradecraft.

Tradecrafts comprise of units of processing called, Analytic, and connect
together via data streams.

Fig 1. General overview.

       1. Users create a tradecraft using an application which communicates
          to any Congregation.

            Application -> _cmdReq_ -> Congregation

       2. Congregation is one per host, it creates the Hallelu.
          
            Congregation -> _HalleluReq_ -> Congregation >create> Hallelu
            Congregation <- _HalleluCfm_ <- Congregation

       3. Hallelu is one per analytic, it creates the Jah.

            Hallelu -> _JahReq_ -> Congregation >create> Jah
            Hallelu <- _JanCfm_ <- Congregation

       5. Hallelu established the streams:
            5.1, instructs the receiving Jah to expect a stream;
            5.2  instructs the sending Jah to create the stream and start
                 sending data (act).

            Halleu -> _StreamReq_ -------------------------------> Jah-recv
            Halleu <- _StreamCfm_ <------------------------------- Jah-recv
            Halleu -> _StreamReq_(act) -> Jah-send
            Halleu <- _StreamCfm_ <------ Jah-send
                                          Jah-send -> _DataReq_ -> Jah-recv
                                          Jah-send <- _DataCfm_ <- Jah-recv

       6. Database confirms that the command is added and active.

            Application <- _cmdCfm_ <- Congregation

       7. User streams the output of an analytic. Commands the Analytic to
          stream the data to the user. This command gets to the Hallelu which
          controls the establishment of the streams from the Jahs to the
          Application.

            Application -> _CmdReq_ -> Congregation
                                       Congregation -> _CmdReq_ -> Halleu

            Application <- _StreamReq_ -> Halleu
            Application <- _StreamReq_ -> Halleu
                                          Halleu -> _StreamReq_(act) -> Jah
                                          Halleu <- _StreamCfm_      <- Jah

# Joining two datastreams.

Joining is enriching a datastream with data from another datastream, to create
a single output of enriched data.

The enrichments can be dataset or datastream.

Example 1, joining a dataset,
    dataset: a lookup table of GPS coordinates tiled over countries;
    datastream: events containing GPS coordinates;
    Output stream: Country added as an extra field for each GPS coordinate.

Example 2, joining a datastream,
    datastream one: TCP outgoing messages;
    datastream two: TCP incoming messages;
    Output stream: Joined TCP messages.

## Joining a finite dataset.

The user identifies fields in both the dataset and the datastream, fields
that join the dataset with the datastream.

The joining fields are hashed to divide the joining process into 256
partitions. Fields can have different names, but their values must be
comparable.
For example,
    A length fields are the same units and cannot be a mixture of centimeter,
    inches and meters.

Four type of Jahs are involved in the joining process:
* JOIN enriches a datasream with information in the dataset.
* ENRICHMENT loads the dataset and routes the dataset partition(s) to
  the JOIN
* PREJOIN routes the datastream partitions(s) to the JOIN.
* POSTJOIN receives the encrihed datastream and performs further processing.

    Fig 2, Different types of Jah (ENRICHMENT, PREJOIN, JOIN, POSTJOIN) are
           involved in this enrichment.

                   (dataset) -> ENRICHMENT
                            (1)     | (2)
                               (3) \ / (4)
        (datastream) -> PREJOIN -> JOIN -> (datastream;enriched) -> POSTJOIN


        1. ENRICHMENT reads the dataset from its source; divides the dataset
        into partitions; sends the data to the JOIN.
    
        2. JOIN receives partitions from the ENRICHMENT. Once the loading is
        complete, a new stream is indicated to the POSTJOIN; Once the POSTJOIN
        stream is established, a new stream is indicated to the PREJOIN and
        the partition key is included in the indication of the stream so the
        PREJOIN know what data to send down this stream.

        3. PREJOIN receives a datastream; divides the datastream into
        partitions; routes the partition to the JOIN.

        4. JOIN enriches the datastream by using the partition key to join
        the datastream and the dataset. The enriched datastream is outputted
        to the POSTJOIN.

    Initially, there is one JOIN and it holds all partitions of the dataset.

    Fig 3, Splitting a JOIN when congestion is detected.

                ENRICHMENT
                   / \
                    | (1)
        PREJOIN -> JOIN (old) -> POSTJOIN (6)
                    (3)
        PREJOIN -> JOIN (new) -> POSTJOIN (5)
               (4)  (2)
        PREJOIN -> JOIN (new) -> POSTJOIN

        1. Congestion is detected by the JOIN. Congestion is indicated to the
        ENRICHMENT
        2. ENRICHMENT creates two new JOIN, each with one half of the
        partitions of the old JOIN; so, the old JOIN is split in two.
        3. The old JOIN continues enriching until the datastream is cancelled.
        4. The new JOIN receives their partitions from the ENRICHMENT; Once the
        loading is complete, a new stream is indicated to the POSTJOI.
        5. Once the POSTJOIN stream is established, a new stream is indicated
        to the PREJOIN and the partition key is included so the PREJOIN knows
        what data to send down the stream.
        6. The old JOIN confirm the cancellation; cancels its datastream
        to the POSTJOIN; deletes itself. Any database resources
        associated with the old JOIN are now freed up for future analytics
        to consume.

    Fig 4, New dataset.
                ENRICHMENT
                    | (1)
                   \ /
        PREJOIN -> JOIN (old) -> POSTJOIN (5)
                    (3)
        PREJOIN -> JOIN (new) -> POSTJOIN
               (4)  (2)

        1. Periodically, the ENRICHMENT receives a new dataset.
        2. ENRICHMENT creates a new JOIN with the same partitions as the old
           JOIN.
        3. The old JOIN continues enriching until the datastream is cancelled.
        4. The new JOIN receives their partitions from the ENRICHMENT, then
           will indicate a new datastream to PREJOIN. The PREJOIN reroutes the
           data on the new datastream and cancels the old datastream.
        5. The old JOIN confirm the cancellation and cancels its datastream
           to the POSTJOIN, then deletes itself. Any database resources
           associated with the old JOIN are now freed up for future analytics
           to use.    
    
## Joining a continious dataset.

    The user identifies an additonal field in the dataset and datastream that
    joins the dataset with the datastream by the time an event occurred.

    The user specifies a window of time in which the joining occurs. ENRICHMENT
    will terminte a JOIN when their partition key for the event timestamp falls
    outside of this window. ENRICHMENT creates a new JOIN for a future
    partition of the event on the timestamp partition key, so future data
    can be sent to a JOIN without waiting for that JOIN to be created and
    the streams established.

    Example of a continious dataset.
        Join request and response events; Join on src and
        dst address and message id, within a window of time. The partition
        key is src + dst + id. The temporal key is event uptime, 


1. <a href="congregation.py">congregation</a> exists per host. Forms the bases of the compute cluster, and starts all other components;
2. <a href="hallelu.py">hallelu</a> exists per host and is the internal point of contact on this host;
3. <a href="jah.py">jah</a> is a partition of functional data residing on a host;
4. <a href="hallelujah.py">hallelujah</a> is the point of contact for a client.