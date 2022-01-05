# Introduction
The discussion here is the communication between the mudp interface (the
reader thread) and the software that is using mudp.
mudp.py has a reader thread, it reads and assembles messages.
Clients use mudp.py to get content into the client's own thread.

# Overall structure of Client and MUDP.
The MUDP class supports one client (thread). Each client has to create a socket
and an MUDP object that manages the reading of messages off of the socket.

The reader thread and client thread both execute within the same Python interpreter.
The interpreter manages thread execution using something called GIL.

## Global Interpreter Lock (GIL)
GIL prevents parallel execution, one thread runs in the interpreter at once. When a thread is running, it holds the GIL and it is release when input/output occurs in the
thread that is running. Threads without input and output, will hold the GIL for the switch interval which is a floating point value representing the duration of time in seconds that a thread will run before being interrupted for a context switch to another thread.

For example, sys.setswitchinterval(1.1)

## Context switch
Context switch is when a thread pauses and another thread resumes, to be the
running thread. A context switch has the overhead of saving the context of
the running thread, and restoring the context for the next thread to run.

## Context switch interval
Context switch interval is the duration for a thread execution without a context switch.

## Critical code sections and locks
A critical block is code that changes a variable that is also changed by code in another thread. For example, in mudp.py, the Reader thread releases received content into the variable "content", and the Client thread deletes the content from the same variable. Normally, a lock is used to guard changes to the "content" variable.

## Why avoid locks.
Locking is I/O and that triggers a context switch, and spending time on context switches takes time away from the overall performance.

## How to avoid locks.
Within the scope of the two threads, locks may be avoided for common variables.
The Producer writes to the variable, and the Consumer reads from the variable.
The crux is variable assigment is not interruptable. The consumer assigns
None, this hands the variable back to the Producer. The Producer assigns a
value into the variable, this hands it back to the Consumer.

# Example, "content" in mudp.py
"content" is the common variable. The Reader builds a new list of content.
When the variable "content" is None, the new list is assigned. The Client
polls the variable "Content", and gets the content and then
sets "content" variable back to None. Reader can now add more content
into the variable while the Client is processing the current content.

# Example, "decodeMsgs" in mudp.py
Reader has a dict of decodeMsg, each is holding chunks of content as well as
the transfer state i.e. regarding chunk ids and etc. Currently both add
to the dict and this can happen at the same time, this needed to change:
* Client adds a decodeMsg after sending, in sendRequest.
* Client deletes decodeMsg after response, in recvResponse.
* Reader adds a decodeMsg when a chunk arrives.

Instead of the above, the Reader thread creates decodeMsg when receiving a
message, this being the only place where decodeMsg is created. recvResponse()
deletes additional messaging that is not the response it is looking for, see
flush(True). Whereas, recv() loads all received content without deleting
anything.

Reader thread deletes decodeMsg when it reads eom.

# Example, "MUDPKey.requestId" in mudp.py
The requestId increments when the MUDPKey is created. MUDPKey is created
by the Client when creating MUDPBuildMsg, and again by the Client in
MUDPBuildMsg.addContent when the last chunk is added to BuildMsg. Multiple
clients using the same MUDP will eventually clash when incrementing requestId,
and therefore each client has its own MUDP.