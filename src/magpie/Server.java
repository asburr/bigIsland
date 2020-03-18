package magpie;

import java.nio.channels.*;
import java.nio.ByteBuffer;
import java.net.SocketAddress;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.LinkedList;
import java.net.InetSocketAddress;

class ServerFutureImp extends ServerFuture {
  private Server server=null;
  public ServerFutureImp(Server server) { this.server=server; }
  public void release(Object client) { this.server.remove((Client)client); }
}
public class Server {
  private AsynchronousServerSocketChannel server=null;
  public boolean shutdown=false;

  // Create a listening socket.
  private int bufferSize=0,headerFlag=0;
  public Server(int port,int bufferSize,int headerFlag) {
    try {
      this.server=AsynchronousServerSocketChannel.open().bind(new InetSocketAddress(port));
    } catch (Exception e) {
      e.printStackTrace();
    }
    this.bufferSize=bufferSize;
    this.headerFlag=headerFlag;
  }

  // Accept a Client connection to this server.
  private Future<AsynchronousSocketChannel> future=null;
  private LinkedList<Client> clients=new LinkedList<Client>();
  public void remove(Client client) { synchronized(this.clients) { this.clients.remove(client); } }
  private ServerFuture serverFuture=new ServerFutureImp(this);
  public Client accept(int mstimeout) {
    if (this.future==null) {
      try {
        this.future=this.server.accept();
      } catch (Exception e) {
        return null;
      }
    }
    try {
      AsynchronousSocketChannel s=this.future.get(mstimeout,TimeUnit.MILLISECONDS);
      this.future=null;
      Client client=new Client(s,this.bufferSize,this.headerFlag,this.serverFuture);
      this.clients.add(client);
      return client;
    } catch (Exception e) {
      return null;
    }
  }

  public void close() {
    try {
      this.server.close();
    } catch (Exception e) {
    }
    this.server=null;
  }

  public static void main(String[] args) {
    if (args.length != 1) {
      System.out.println("Usage: <listening port>");
      return;
    }
    System.out.println("Server listening on port "+args[0]);
    Server server=new Server(Integer.parseInt(args[0]),100,0xffee);
    Client client=null;
    int count=0;
    while (true) {
      client=server.accept(10);
      if (client!=null) {
        System.out.println("Server accepted connection from "+client.addresses()+" sending="+count);
        client.sendBuf.putInt(count);
        client.write();
        while (!client.read()) {
          System.out.println("Waiting for response from "+client.addresses());
          try { Thread.sleep(1000); } catch(Exception e) {}
        }
        count++;
        int i=client.recvBuf.getInt();
        if (i!=count) {
          System.out.println("Bad response from client got="+i+" expecting="+count);
        } else {
          System.out.println("Response from client got="+i);
        }
      }
    }
  }
}
