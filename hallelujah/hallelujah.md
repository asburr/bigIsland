# Hallelujah

Hallelujah is a translation of a Hebrew phrase which means "praise ye Jah!". The word hallel in Hebrew means a joyous praise in song. The word Yah is a shortened form of YHWH (Yahweh in modern English) meaning "They Who Make That Which Has Been Made", or "They who Bring into Existence Whatever Exists". It's also a song written by Canadian singer Leonard Cohen, originally released on his album Various Positions (1984). Cohen took about five years to write the song, and reconfigured it numerous times for performances.

Hallelujah is a massively parallelized analytics engine for large data sets that's quick to reconfigure for different results.

1. <a href="congregation.py">congregation</a> exists per host. Forms the bases of the compute cluster, and starts all other components;
2. <a href="hallelu.py">hallelu</a> exists per host and is the internal point of contact on this host;
3. <a href="jah.py">jah</a> is a partition of functional data residing on a host;
4. <a href="hallelujah.py">hallelujah</a> is the point of contact for a client.
