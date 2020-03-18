package magpie;

import java.io.BufferedReader; 
import java.io.IOException; 
import java.io.InputStreamReader; 
import java.nio.CharBuffer;

public class Cli {
  Client client=null;
  public Cli(String host, int port) {
    Client client=new Client(host,port,100,0xffee);
  }
  public void stdin() { try {
    System.out.print(">"); System.out.flush();
    BufferedReader reader=new BufferedReader(new InputStreamReader(System.in)); 
    String line = reader.readLine(); 
    while (line!=null) {
      if (line.equals("x")) return;
      client.sendBuf_SetString(line);
      client.write();
      try { Thread.sleep(100); } catch(Exception e) {}
      while (!client.read()) {
        System.out.println("Waiting for response from server");
        try { Thread.sleep(1000); } catch(Exception e) {}
      }
      System.out.println(client.recvBuf_GetString());
      System.out.print(">"); System.out.flush();
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
