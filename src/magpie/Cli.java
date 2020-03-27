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
    long before=0L,after=0L;
    System.out.print(">"); System.out.flush();
    BufferedReader reader=new BufferedReader(new InputStreamReader(System.in)); 
    String line = reader.readLine(); 
    String lastLine=null;
    String lastResp=null;
    long ld=0L;
    while (line!=null) {
      if (line.equals("x")) return;
      if (line.startsWith("*")) {
        int count=Integer.parseInt(line.substring(2));
        before=System.nanoTime();
        while (count>0) {
          client.sendBuf_String(lastLine);
          while (!client.read(100,TimeUnit.MILLISECONDS));
          client.recvBuf_GetString(-1);
          count--;
        }
        after=System.nanoTime();
      } else {
        before=System.nanoTime();
        client.sendBuf_String(line);
        while (!client.read(100,TimeUnit.MILLISECONDS));
        after=System.nanoTime();
        System.out.print(client.recvBuf_GetString(-1));
        lastLine=line;
      }
      if (client.shutdown) { System.out.println("Server closed"); return; }
      long d=(after-before)/100000;
      long p=0L;
      if (ld > 0 && d > ld ) p=d/ld; else p=-(ld/d);
      System.out.print(String.format("%03d",d)+" "+p+">"); System.out.flush();
      ld=d;
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
