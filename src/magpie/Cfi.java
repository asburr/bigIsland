package magpie;

import java.io.BufferedReader; 
import java.io.File;
import java.io.IOException; 
import java.io.InputStreamReader; 
import java.io.FileReader;
import java.util.concurrent.TimeUnit;

public class Cfi {
  Client client=null;
  File indir=null;
  boolean consume=false;
  public Cfi(String host, int port, String indir, boolean consume) {
    this.client=new Client(host,port,100,0xffee);
    this.indir=new File(indir);
    this.consume=consume;
  }
  public void readFiles() { try {
    while (true) {
      for (File f: this.indir.listFiles()) {
        this.readFile(f);
        if (this.consume) f.delete();
      }
      if (!this.consume) return;
    }
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
  public void readFile(File f) { try {
    BufferedReader reader=new BufferedReader(new FileReader(f)); 
    String line = reader.readLine(); 
    client.sendBuf_String("M"); // Machine interface.
    while (line!=null) {
      client.sendBuf_String(line);
      if (client.read(0,TimeUnit.MILLISECONDS)) {
        String resp=client.recvBuf_GetString(-1);
        // Not expecting any response, output to stderr.
        if (resp.length()>0) System.err.print(resp);
      }
      line = reader.readLine(); 
    }
    reader.close();
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
  public static void main(String[] args) { try {
    if (args.length != 4) {
      System.out.println("Usage: <server host> <server port> <directory> (comsume|once)\ni.e. localhost 9001 filesDir once");
      return;
    }
    Cfi cfi=new Cfi(args[0],Integer.parseInt(args[1]),args[2],args[3].equals("consume"));
    cfi.readFiles();
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
}
