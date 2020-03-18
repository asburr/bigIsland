package hallelulajah;

import java.util.concurrent.ConcurrentSkipListMap;
import magpie.Server;
import magpie.Client;
import java.util.concurrent.ExecutorService; 
import java.util.concurrent.Executors; 
import java.util.LinkedList;

class Yahweh implements Runnable {

  public boolean shutdown=false;

  private Client client=null;
  private Hallelulajah hall=null;
  public Yahweh(Client client,Hallelulajah hall) {
    this.client=client;
    this.hall=hall;
  }

  private Table table=null;
  private Row row=null;
  private String key=null;
  public void run() {
    while (!this.shutdown) {
      if (!client.read()) {
        try { Thread.sleep(10); } catch(Exception e) {}
        continue;
      }
      String cmd=this.client.recvBuf_GetString();
      String a[]=cmd.split(",");
      switch (a[0].charAt(0)) {
      case 'x': return;
      case 'p': { // Connect to table
        this.table=hall.getTable(a[1]);
        if (this.table!=null) this.client.sendBuf_String("Connected to table "+this.table.name);
        else this.client.sendBuf_String("Failed to connect to table");
      }
      case '+': { // Add table
        this.table=hall.newTable(a[1]);
        this.client.sendBuf_String("Table created (or exists) "+this.table.name);
      }
      case '-': { // Delete table
        if (this.table==null) { this.client.sendBuf_String("Connect (c) to table"); continue; }
        if (this.hall.delTable(this.table.name,this.table)) this.client.sendBuf_String("Table deleted "+this.table.name);
        else this.client.sendBuf_String("Table does not exist could already be deleted "+this.table.name);
        this.table=null;
      }
      case 'a': { // Add row
        if (this.table==null) { this.client.sendBuf_String("Connect (c) to table"); continue; }
        if (a.length < 2) { this.client.sendBuf_String("usage: a,<key>,<row>"); continue; }
        this.key=a[1];
        this.row=new Row(this.key.substring(2+this.key.length()));
        Row r=this.table.addRow(this.key,this.row);
        if (r!=null) this.client.sendBuf_String("Row already at this key");
        else this.client.sendBuf_String("Row added");
      }
      case 'd': { // Delete row
        if (this.table==null) { this.client.sendBuf_String("Connect (c) to table"); continue; }
        if (a.length < 2) { this.client.sendBuf_String("usage: d,<key>"); continue; }
        this.key=a[1];
        this.row=null;
        this.table.delRow(this.key);
      }
      case 'q': { // Query table
        if (this.table==null) { this.client.sendBuf_String("Please connect to table"); continue; }
        if (a.length < 2) { this.client.sendBuf_String("usage: q,<key>"); continue; }
        this.key=a[1];
        this.row=null;
        this.row=this.table.getRow(this.key);
        this.client.sendBuf_String(this.row.s);
      }
    }
    }
  }
}

class Row {
  public String s;
  public Row(String s) { this.s=s; }
}

class Table {
  String name=null;
  ConcurrentSkipListMap<String,Row> rows=new ConcurrentSkipListMap<String,Row>();
  public Table(String name) { this.name=name; }
  public Row addRow(String key,Row row) {
    return this.rows.putIfAbsent(key,row);
  }
  public void delRow(String key) {
    this.rows.remove(key);
  }
  public Row getRow(String key) {
    return this.rows.get(key);
  }
}

public class Hallelulajah {

  Server server=null;
  public Hallelulajah(String host, int port) {
    this.server=new Server(port,100,0xffee);
  }

  LinkedList<Yahweh> jahs=new LinkedList<Yahweh>();
  public void start() {
    ExecutorService pool=Executors.newCachedThreadPool();
    while (true) {
      Client client=server.accept(100);
      if (client!=null) {
        System.out.println("Server accepted connection from "+client.addresses());
        Yahweh jah=new Yahweh(client,this);
        this.jahs.add(jah);
        pool.execute(jah); 
      }
    }
    //pool.shutdown();     
  }

  ConcurrentSkipListMap<String,Table> tables=new ConcurrentSkipListMap<String,Table>();
  public Table getTable(String name) { return this.tables.get(name); }
  public Table newTable(String name) {
    Table n=new Table(name);
    Table t=this.tables.putIfAbsent(name,n);
    if (t!=null) return t;
    return n;
  }
  public boolean delTable(String name,Table table) { return this.tables.remove(name,table); }

  public static void main(String[] args) { try {
    if (args.length != 2) {
      System.out.println("Usage: <listening host> <listening port>\ni.e. localhost 9001");
      return;
    }
    Hallelulajah h=new Hallelulajah(args[0],Integer.parseInt(args[1]));
    h.start();
  } catch(Exception e) {
    e.printStackTrace();
  }
  }
}
