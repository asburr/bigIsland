package magpie;

import java.nio.channels.*;
import java.nio.ByteBuffer;
import java.net.SocketAddress;
import java.net.InetSocketAddress;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

class Client {

  AsynchronousSocketChannel client=null;
  InetSocketAddress listener=null;
  public SocketAddress address=null;
  public ByteBuffer sendBuf=null;
  public ByteBuffer recvBuf=null;
  int headerFlag=0;
  public boolean shutdown=false;

  public Client(AsynchronousSocketChannel client,int bufferSize,int headerFlag) {
    try {
      this.client=client;
      this.headerFlag=headerFlag;
      this.address=this.client.getLocalAddress();
      this.sendBuf=ByteBuffer.allocate(bufferSize);
      this.recvBuf=ByteBuffer.allocate(bufferSize);
      this.resetSendBuf();
    } catch (Exception e) {
      System.err.println("Failed to create client");
      this.close();
      return;
    }
  }
  public Client(String host, int port,int bufferSize,int headerFlag) {
    try {
      this.client=AsynchronousSocketChannel.open();
      this.listener=new InetSocketAddress(host, port);
      Future future = client.connect(this.listener);
      future.get(100,TimeUnit.MILLISECONDS);
      this.headerFlag=headerFlag;
      this.address=this.client.getLocalAddress();
      this.recvBuf=ByteBuffer.allocate(bufferSize);
      this.sendBuf=ByteBuffer.allocate(bufferSize);
      this.resetSendBuf();
    } catch (Exception e) {
      System.err.println("Failed to connect to listener "+this.listener);
      this.close();
      return;
    }
  }
  private void resetSendBuf() {
    this.sendBuf.clear();
    this.sendBuf.putInt(headerFlag);
    this.sendBuf.putInt(0); // Dummy length.
  }

  public void close() {
    if (this.shutdown) return;
    this.shutdown=true;
    try {
      this.client.close();
      this.client=null;
    } catch (Exception e) {
      System.err.println("Failed to close socket "+this.address);
    }
    this.recvBuf=null;
    this.sendBuf=null;
    this.address=null;
  }

  // Blocking write.
  // Write length first, then buffer.
  public void write() {
    int size=this.sendBuf.position()-8;
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
    if (size+8 != written) {
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
    this.recvBuf.flip();
    return true;
  }
  public static void main(String[] args) { try {
    if (args.length != 2) {
      System.out.println("Usage: <client listening port>\ni.e. localhost 9001");
      return;
    }
    Client client=new Client(args[0],Integer.parseInt(args[1]),100,0xffee);
    while (!client.read()) {
      System.out.println("Waiting for response from client");
      try { Thread.sleep(1000); } catch(Exception e) {}
    }
    int i=client.recvBuf.getInt()+1;
    client.sendBuf.putInt(i);
    client.write();
    client.close();
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
}

