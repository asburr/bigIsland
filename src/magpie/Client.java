package magpie;

import java.nio.channels.*;
import java.nio.ByteBuffer;
import java.net.SocketAddress;
import java.net.InetSocketAddress;
import java.net.StandardSocketOptions;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.ExecutionException;

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
  private String sendString=null;
  public void sendBuf_SetString(String s) {
    int space=this.sendBuf.capacity()-this.sendBuf.position();
    if (s.length() > space) s=s.substring(0,space);
    this.sendBuf.put(s.getBytes());
  }
  public void sendBuf_String(String s) { this.sendString=s; this.write(); }
  public String recvBuf_GetString(int l) { 
    if (l==-1) l=this.recvBuf.remaining();
    if (l==0) return "";
    byte[] bytes=new byte[l];
    this.recvBuf.get(bytes);
    return new String(bytes);
  }

  public ByteBuffer recvBuf=null;
  int headerFlag=0;
  public boolean shutdown=false;

  public Client(AsynchronousSocketChannel client,int bufferSize,int headerFlag,ServerFuture server) {
    try {
      client.setOption(StandardSocketOptions.SO_KEEPALIVE, true);
/*
      client.setOption(StandardSocketOptions.TCP_NODELAY, true);
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
      client.setOption(StandardSocketOptions.SO_KEEPALIVE, true);
/*
      client.setOption(StandardSocketOptions.TCP_NODELAY, true);
      client.setOption(StandardSocketOptions.SO_REUSEADDR, true)
      client.setOption(StandardSocketOptions.SO_RCVBUF, 16 * 1024);
*/
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
      if (this.server!=null) this.server.release(this);
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
    if (this.sendString!=null) this.sendBuf.putInt(4,size+this.sendString.length());
    else this.sendBuf.putInt(4,size);
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
    if (this.sendString!=null) {
      future=this.client.write(ByteBuffer.wrap(this.sendString.getBytes()));
      written=0;
      while (!this.shutdown) {
        try {
          written=future.get();
          break;
        } catch(InterruptedException e) {
        } catch(Exception e) {
          e.printStackTrace();
        }
      }
      if (this.sendString.length() != written) {
        System.err.println("Failed to send all bytes, size="+this.sendString.length()+" written="+written);
      }
      this.sendString=null;
      this.resetSendBuf();
    }
  }

  // Timeout or Blocking read.
  private Future<Integer> futureHdr=null;
  private Future<Integer> futureBdy=null;
  private int bdySize=0;
  public boolean read(long timeout, TimeUnit unit) {
    if (this.shutdown) return false;
    //
    // Read header
    //
    int read=0;
    if (this.bdySize==0 && this.futureHdr==null && this.futureBdy==null) {
      this.recvBuf.clear();
      this.recvBuf.limit(8);
      this.futureHdr=this.client.read(this.recvBuf);
    }
    if (this.bdySize==0 && this.futureHdr!=null) {
      read=0;
      while (!this.shutdown) {
        try {
          read=this.futureHdr.get(timeout,unit);
          this.futureHdr=null;
          break;
        } catch(TimeoutException e) {
          return false;
        } catch(InterruptedException e) {
        } catch(ExecutionException e) {
          this.close();
          return false;
        } catch(Exception e) {
          e.printStackTrace();
          return false;
        }
      }
      if (read==0) return false;
      if (read==-1) { this.close(); return false; }
      if (this.recvBuf.limit() != read) {
        System.err.println("Failed to read header, size="+this.recvBuf.limit()+" read="+read);
      }
      this.recvBuf.rewind();
      int flag=this.recvBuf.getInt();
      if (flag != this.headerFlag) {
        System.err.println("Failed to read header, flag="+flag+" expecting="+this.headerFlag);
        return false;
      }
      this.bdySize=this.recvBuf.getInt();
      if (this.bdySize==0) return false;
    }
    //
    // Read body
    //
    if (this.bdySize>0 && this.futureBdy==null) {
      this.recvBuf.clear();
      if (this.bdySize <= this.recvBuf.capacity()) {
        this.recvBuf.limit(this.bdySize);
        this.bdySize=0;
      } else {
        this.recvBuf.limit(this.recvBuf.capacity());
        this.bdySize-=this.recvBuf.capacity();
      }
      this.futureBdy=this.client.read(this.recvBuf);
    }
    if (this.futureBdy!=null) {
      read=0;
      while (!this.shutdown) {
        try {
          read=this.futureBdy.get(timeout,unit);
          this.futureBdy=null;
          break;
        } catch(TimeoutException e) {
          return false;
        } catch(InterruptedException e) {
        } catch(Exception e) {
          e.printStackTrace();
          return false;
        }
      }
      if (read==0) return false;
      if (read==-1) { this.close(); return false; }
      if (this.recvBuf.limit() != read) {
        System.err.println("Failed to read body, size="+read+" expecting="+this.recvBuf.limit());
      }
      this.recvBuf.flip();
      return true;
    }
    return false;
  }
  public static void main(String[] args) { try {
    if (args.length != 2) {
      System.out.println("Usage: <client listening port>\ni.e. localhost 9001");
      return;
    }
    Client client=new Client(args[0],Integer.parseInt(args[1]),100,0xffee);
    while (!client.read(1,TimeUnit.SECONDS)) {
      System.out.println("Waiting for response from client");
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

