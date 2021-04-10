package magpie;

import java.io.RandomAccessFile;
import java.io.BufferedReader; 
import java.io.File;
import java.io.IOException; 
import java.io.InputStreamReader; 
import java.io.FileReader;
import java.util.concurrent.TimeUnit;
import java.util.LinkedList;
import java.lang.Math;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

class Worker implements Runnable {
  Client client=null;
  public boolean shutdown=false;
  public Worker(String host, int port) {
    this.client=new Client(host,port,100,0xffee);
    this.client.sendBuf_String("M"); // Machine interface.
  }
  public void close() {
    this.client.close();
  }
  File f;
  long start,end;
  public void setup(File f,long start, long end) {
    this.f=f;
    this.start=start;
    this.end=end;
  }
  public void run() { try {
    RandomAccessFile in=new RandomAccessFile(this.f,"r");
    in.seek(start);
    String line=in.readLine(); // Ignore first partial line.
    line=in.readLine(); 
    while (line!=null) {
      client.sendBuf_String(line);
      if (client.read(0,TimeUnit.MILLISECONDS)) {
        String resp=client.recvBuf_GetString(-1);
        // Not expecting any response, output to stderr.
        if (resp.length()>0) System.err.print(resp);
      }
      if (in.getFilePointer() > this.end) break;
      line=in.readLine(); 
    }
    if (client.read(0,TimeUnit.MILLISECONDS)) {
      String resp=client.recvBuf_GetString(-1);
    }
    in.close();
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
}

public class Cfi {

  File indir=null;
  long fileBlock=9000l;
  boolean consume=false;
  ExecutorService pool=null;
  String host=null;
  int port=0;
  LinkedList<Worker> workers=new LinkedList<Worker>();

  public Cfi(String host, int port, String indir, boolean consume) {
    this.indir=new File(indir);
    this.host=host;
    this.port=port;
    this.consume=consume;
  }
  private void procs() {
    this.maxworkers=Runtime.getRuntime().availableProcessors();
  }
  public void readFiles() {
    this.pool=Executors.newCachedThreadPool();
    int workers=0;
    try {
      while (true) {
        for (File f: this.indir.listFiles()) {
          if (f.isHidden()) continue;
          this.procs();
          this.readFile(f);
          if (this.consume) f.delete();
        }
        if (!this.consume) break;
      }
    } catch (Exception e) {
      e.printStackTrace();
    }
    this.pool.shutdown();
  }
  int maxworkers=1;
  public void readFile(File f) {
    long l=f.length();
    long block=l/this.fileBlock;
    while (this.maxworkers==0) try {
      Thread.sleep(100);
      this.procs();
    } catch(Exception ignore) {}
    block=Math.min(this.maxworkers,block);
    long size=l/block;
    while (size < l) {
      Worker worker=this.workers.removeFirst();
      if (worker==null) {
        worker=new Worker(this.host,this.port);
      }
      long nsize=size+block;
      worker.setup(f,size,nsize);
      pool.execute(worker);
    }
  }
  public static void main(String[] args) { try {
    if (args.length != 4) {
      System.out.println("Usage: <server host> <server port> <directory> (comsume|once) [\ni.e. localhost 9001 filesDir once");
      return;
    }
    Cfi cfi=new Cfi(args[0],Integer.parseInt(args[1]),args[2],args[3].equals("consume"));
    cfi.readFiles();
  } catch (Exception e) {
    e.printStackTrace();
  }
  }
}
