package magpie;

import java.nio.channels.*;
import java.nio.ByteBuffer;
import java.net.SocketAddress;
import java.util.concurrent.Future;

class Client {

  AsynchronousSocketChannel client=null;
  SocketAddress address=null;
  public ByteBuffer sendBuf=null;
  public ByteBuffer recvBuf=null;
  int headerFlag=0;
  public boolean shutdown=false;

  public Client(AsynchronousSocketChannel client,int bufferSize,int headerFlag) {
    this.client=client;
    this.headerFlag=headerFlag;
    try {
      this.address=this.client.getLocalAddress();
    } catch (Exception e) {
      System.err.println("Failed to get socket address");
    }
    this.sendBuf=ByteBuffer.allocate(bufferSize);
    this.resetSendBuf();
  }
  private void resetSendBuf() {
    this.sendBuf.putInt(headerFlag);
    this.sendBuf.putInt(0); // Dummy length.
  }

  public void close() {
    try {
      this.client.close();
    } catch (Exception e) {
      System.err.println("Failed to close socket "+this.address);
    }
    this.recvBuf=null;
    this.sendBuf=null;
  }

  // Blocking write.
  // Write length first, then buffer.
  public void write() {
    int size=this.sendBuf.position();
    this.sendBuf.flip();
    this.sendBuf.putInt(4,size);
    Future<Integer> future=this.client.write(this.sendBuf);
    int written=0;
    while (!this.shutdown) {
      try {
        written=future.get();
        break;
      } catch(InterruptedException e) {
      } catch(Exception e) {
        e.printStackTrace();
      }
    }
    if (size != written) {
      System.err.println("Failed to send all bytes, size="+size+" written="+written);
    }
    this.resetSendBuf();
  }

  public boolean read() {
    //
    // Read header
    //
    this.recvBuf.clear();
    int size=8;
    this.recvBuf.limit(size);
    Future<Integer> future=this.client.read(this.recvBuf);
    int read=0;
    while (!this.shutdown) {
      try {
        read=future.get();
        break;
      } catch(InterruptedException e) {
      } catch(Exception e) {
        e.printStackTrace();
      }
    }
    if (read==0) return false;
    if (size != read) {
      System.err.println("Failed to read header, size="+size+" read="+read);
    }
    this.recvBuf.rewind();
    int flag=this.recvBuf.getInt();
    if (flag != this.headerFlag) {
      System.err.println("Failed to read header, flag="+flag+" expecting="+this.headerFlag);
      return false;
    }
    size=this.recvBuf.getInt();
    if (size==0) return false;
    //
    // Read body
    //
    this.recvBuf.clear();
    this.recvBuf.limit(size);
    future=this.client.read(this.recvBuf);
    while (!this.shutdown) {
      try {
        read=future.get();
        break;
      } catch(InterruptedException e) {
      } catch(Exception e) {
        e.printStackTrace();
      }
    }
    if (read==0) return false;
    if (size != read) {
      System.err.println("Failed to read body, size="+read+" expecting="+size);
    }
    return true;
  }
}

