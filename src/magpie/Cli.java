package magpie;

import java.io.BufferedReader; 
import java.io.IOException; 
import java.io.InputStreamReader; 
import java.nio.CharBuffer;
import java.util.concurrent.TimeUnit;

public class Cli {
  Client client=null;
  public Cli(String host, int port) {
    this.client=new Client(host,port,100,0xffee);
  }
  public void stdin() { try {
    System.out.print(">"); System.out.flush();
    BufferedReader reader=new BufferedReader(new InputStreamReader(System.in)); 
    String line = reader.readLine(); 
    while (line!=null) {
      if (line.equals("x")) return;
      client.sendBuf_String(line);
      try { Thread.sleep(100); } catch(Exception e) {}
      while (client.read(100,TimeUnit.MILLISECONDS)) {
        System.out.print(client.recvBuf_GetString(-1));
      }
      if (client.shutdown) { System.out.println("Server closed"); return; }
      System.out.print(">"); System.out.flush();
      line = reader.readLine(); 
    }
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
  public static void main(String[] args) { try {
    if (args.length != 2) {
      System.out.println("Usage: <server host> <server port>\ni.e. localhost 9001");
      return;
    }
    Cli cli=new Cli(args[0],Integer.parseInt(args[1]));
    cli.stdin();
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
}
