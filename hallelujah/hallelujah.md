# Hallelujah

Hallelujah is a translation of a Hebrew phrase which means "praise ye Jah!". The word hallel in Hebrew means a joyous praise in song. The word Yah is a shortened form of YHWH (Yahweh in modern English) meaning "They Who Make That Which Has Been Made", or "They who Bring into Existence Whatever Exists". It's also a song written by Canadian singer Leonard Cohen, originally released on his album Various Positions (1984). Cohen took about five years to write the song, and reconfigured it numerous times for performances.

Hallelujah is a massively parallelized analytics engine for large data sets that's quick to reconfigure for different results.

Hallelujah manages work in streams. External input is processed by Jahs too,
these Jahs report backlogs to their Hallelu which in turn creates more Jahs.
Some Jahs hold transient data which is distributed to other Jahs and not
held within the Jah. These Jahs can be stopped, and stopping a Jah is the
responsibility of the Hallelu, and again is triggered by the backlog reporting.
The Congregation has the ability to shutdown transient Jahs too, to free up
resources for additional streams. The end user can decrease the capcity of
other streams when Hallelu cannot create a new stream.

Other Jahs are holding data that is persistant. There is a copy
of the data on disk, and a Jah is restarted with the data from disk.
Restart occurs when an outgoing stream is requested. Also, a restart occurs
when an incoming stream is requested, and the Jah will update the data on
disk from the incoming stream of data.

1. <a href="congregation.py">congregation</a> exists per host. Forms the bases of the compute cluster, and starts all other components;
2. <a href="hallelu.py">hallelu</a> exists per host and is the internal point of contact on this host;
3. <a href="jah.py">jah</a> is a partition of functional data residing on a host;
4. <a href="hallelujah.py">hallelujah</a> is the point of contact for a client.

 Hallelu are less resource needy, and it's assumed they will run on the spare
 CPU cycles on a host with a full deployment of Jahs. Jah are single
 threaded, and cannot use more than one CPU and generally use less than a full
 CPU, and the Congregation starts no more than one Jah per CPU, so there's
 spare capacity for Hallelus to run too.



