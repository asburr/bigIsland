package magpie;

import java.nio.channels.*;
import java.nio.ByteBuffer;
import java.net.SocketAddress;
import java.net.InetSocketAddress;
import java.net.StandardSocketOptions;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.nio.CharBuffer;

public class Client {

  private AsynchronousSocketChannel client=null;
  private boolean clientToServer=true;
  public String addresses() {
    if (this.client==null) return "Not connected";
    try {
      if (clientToServer) return this.client.getRemoteAddress()+"=>"+this.client.getLocalAddress();
      return this.client.getLocalAddress()+"=>"+this.client.getRemoteAddress();
    } catch (Exception ignore) {
      return ignore.getMessage();
    }
  }
  InetSocketAddress listener=null;
  private ServerFuture server=null;

  public ByteBuffer sendBuf=null;
  public void sendBuf_SetString(String s) { this.sendBuf.asCharBuffer().put(s); }
  public void sendBuf_String(String s) { this.sendBuf_SetString(s); this.write(); }
  public String recvBuf_GetString() { return this.recvBuf.asCharBuffer().toString(); }

  public ByteBuffer recvBuf=null;
  int headerFlag=0;
  public boolean shutdown=false;

  public Client(AsynchronousSocketChannel client,int bufferSize,int headerFlag,ServerFuture server) {
    try {
      client.setOption(StandardSocketOptions.SO_KEEPALIVE, true);
      client.setOption(StandardSocketOptions.TCP_NODELAY, true);
/*
      client.setOption(StandardSocketOptions.SO_REUSEADDR, true)
      client.setOption(StandardSocketOptions.SO_RCVBUF, 16 * 1024);
*/
      this.server=server;
      this.client=client;
      this.headerFlag=headerFlag;
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
      this.clientToServer=false;
      this.client=AsynchronousSocketChannel.open();
      this.listener=new InetSocketAddress(host, port);
      Future future = client.connect(this.listener);
      future.get(100,TimeUnit.MILLISECONDS);
      this.headerFlag=headerFlag;
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
      System.err.println("Client closed:"+this.addresses());
      this.server.release(this);
    } catch (Exception e) {
      System.err.println("Failed to release from server "+this.addresses());
    }
    try {
      this.client.close();
      this.client=null;
    } catch (Exception e) {
      System.err.println("Failed to close socket "+this.addresses());
    }
    this.recvBuf=null;
    this.sendBuf=null;
  }

  // Blocking write.
  // Write length first, then buffer.
  public void write() {
    if (this.shutdown) return;
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
    if (this.shutdown) return false;
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
    if (read==-1) { this.close(); return false; }
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
    if (read==-1) { this.close(); return false; }
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

