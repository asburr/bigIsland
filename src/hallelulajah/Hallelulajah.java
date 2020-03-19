package hallelulajah;

import java.io.File;
import java.io.RandomAccessFile;
import java.io.IOException;
import java.io.EOFException;
import java.io.FileNotFoundException;
import java.util.concurrent.ConcurrentSkipListMap;
import magpie.Server;
import magpie.Client;
import java.util.concurrent.ExecutorService; 
import java.util.concurrent.Executors; 
import java.util.LinkedList;
import java.util.concurrent.TimeUnit;
import java.util.UUID;
import java.util.ArrayList;

class JournalO {
  private File journal=null;
  private RandomAccessFile j=null;
  public JournalO(File dir) {
    try {
      this.journal=new File(dir+File.separator+"J_"+UUID.randomUUID());
      this.j=new RandomAccessFile(this.journal,"wd");
// Append not needed we are creating a new file every occurance.
// this.j.seek(this.j.length());
    } catch (FileNotFoundException e) {
      e.printStackTrace();
    }
  }
  public void write(char cmd, String key, Row row) {
    try {
      this.j.writeLong(System.nanoTime());
      this.j.writeChar(cmd);
      this.j.writeUTF(key);
      this.j.writeUTF(row.s);
    } catch(Exception e) {
      e.printStackTrace();
      this.close();
    }
  }
  public void close() {
    try {
      this.journal=null;
      this.j.close();
      this.j=null;
    } catch (Exception e) {
    }
  }
}

class JournalI {
  private File journal=null;
  private RandomAccessFile j=null;
  public JournalI(File file) {
    this.journal=file;
    try {
      this.j=new RandomAccessFile(this.journal,"r");
    } catch(Exception e) {
      e.printStackTrace();
    }
  }
  public long time;
  public char cmd='?';
  public String key=null;
  public Row row=new Row("");
  public boolean eof=false;
  public void next() {
    try {
      this.time=this.j.readLong();
      this.cmd=this.j.readChar();
      this.key=this.j.readUTF();
      this.row.set(this.j.readUTF());
    } catch (EOFException e) {
      this.eof=true;
    } catch (IOException e) {
      e.printStackTrace();
      this.eof=true;
    }
  }
  // compare < 0, when this started before i
  // compare > 0, when this started after i
  // compare = 0, when this started at the same time at i.
  public long compare(JournalI i) {
    return this.time - i.time;
  }
}

// Maintains an ordered array of Journal files, ordered by start TimeStamp
// of transaction.
class JournalIs {
  public JournalIs(File dir) {
    for (File f: dir.listFiles()) {
      if (!f.getName().startsWith("J_")) continue;
      JournalI j=new JournalI(f);
      j.next();
      if (j.eof) continue;
      this.insert(j);
    }
  }
  private ArrayList<JournalI> a=new ArrayList<JournalI>();
  private void insert(JournalI j) {
    for (int i=0;i<a.size();i++) {
      if (a.get(i).compare(j) < 0) continue; // i started before j.
      this.a.add(i,j); // i started after or at the same time as j.
      return;
    }
  }
  public JournalI get() {
    if (a.size()==0) return null;
    return a.remove(0);
  }
  public void put(JournalI j) {
    j.next();
    if (j.eof) return;
    this.insert(j);
  }
}

class Yahweh implements Runnable {

  private Client client=null;
  private Hallelulajah hall=null;
  private JournalO j=null;

  public Yahweh(Client client,Hallelulajah hall) {
    this.client=client;
    this.hall=hall;
    this.j=new JournalO(hall.dir);
  }

  private Table table=null;
  private Row row=null;
  private String key=null;
  public void run() {
    while (!this.client.shutdown) {
      if (!client.read(10,TimeUnit.MILLISECONDS)) {
        continue;
      }
      String cmd=this.client.recvBuf_GetString(-1);
      if (cmd.length()==0) continue;
      String a[]=cmd.split(",",-1);
      switch (a[0].charAt(0)) {
      case 'x': {
        this.client.sendBuf_String("Success : exiting connection\n");
        return;
      }
      case 'c': { // Connect to table
        if (a.length == 1) {
          if (this.table==null) this.client.sendBuf_String("Success : not connected to any table\n");
          else this.client.sendBuf_String("Success : connected to table name "+this.table.name+"\n");
          continue;
        }
        if (a.length != 2) { this.client.sendBuf_String("Usage : c,<table name>\n"); continue; }
        this.table=hall.getTable(a[1]);
        if (this.table!=null) this.client.sendBuf_String("Success : connected to table name "+this.table.name+"\n");
        else this.client.sendBuf_String("Fail : no such table name "+a[1]+"\n");
        break;
      }
      case '+': { // Add table
        if (a.length != 2) { this.client.sendBuf_String("usage: +,<table name>\n"); continue; }
        this.table=hall.newTable(a[1]);
        this.client.sendBuf_String("Success : Table created or already exists with the name "+this.table.name+"\n");
        this.j.write('+',this.table.name,null);
        break;
      }
      case '-': { // Delete table
        if (a.length != 1) { this.client.sendBuf_String("Usage : -\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : Please connect (c) to a table\n"); continue; }
        if (this.hall.delTable(this.table.name,this.table)) {
          this.j.write('-',this.table.name,null);
          this.client.sendBuf_String("Success : table "+this.table.name+" deleted\n");
        } else this.client.sendBuf_String("Fail : Table does not exist could already be deleted "+this.table.name+"\n");
        this.table=null;
        break;
      }
      case 'a': { // Add row
        if (a.length != 3) { this.client.sendBuf_String("usage : a,<key>,<data>\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect (c) to a table\n"); continue; }
        this.key=a[1];
        this.row=new Row(this.key.substring(2+this.key.length()));
        Row r=this.table.addRow(this.key,this.row);
        if (r!=null) this.client.sendBuf_String("Fail : row exists already at this key\n");
        else {
          this.j.write('a',this.key,this.row);
          this.client.sendBuf_String("Success : row added\n");
        }
        break;
      }
      case 'd': { // Delete row
        if (a.length != 2) { this.client.sendBuf_String("Usage : d,<key>\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect (c) to a table\n"); continue; }
        this.key=a[1];
        this.row=this.table.delRow(this.key);
        if (this.row==null) { this.client.sendBuf_String("Fail : row does not exist\n"); continue; }
        this.j.write('d',this.key,this.row);
        this.row=null;
        this.client.sendBuf_String("Success : deleted row at "+this.key+"\n");
        break;
      }
      case 'q': { // Query table
        if (a.length != 2) { this.client.sendBuf_String("Usage : q,<key>\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect to a table\n"); continue; }
        this.key=a[1];
        this.row=null;
        this.row=this.table.getRow(this.key);
        this.client.sendBuf_String(this.row.s);
        break;
      }
      default: {
        this.client.sendBuf_String("Usage: [x,c,+,-,a,d,q]\nDescription:"+
"\nx : exit :"+
"\nc <table name> : connect to table : table must already exist"+
"\n+ <table name> : add table : no error when table already exists"+
"\n- : remove table : connect(c)"+
"\na <key>,<data> : add row : connect(c)"+
"\nd <key> : deletes row and returns row data : connect(c)"+
"\nq <key> : return row data : connect(c)"+
"\n"
);
        break;
      }
    }
    }
  }
}

class Row {
  public String s;
  public Row(String s) { this.s=s; }
  public void set(String s) { this.s=s; }
}

class Table {
  String name=null;
  ConcurrentSkipListMap<String,Row> rows=new ConcurrentSkipListMap<String,Row>();
  public Table(String name) { this.name=name; }
  public Row addRow(String key,Row row) {
    return this.rows.putIfAbsent(key,row);
  }
  public Row delRow(String key) {
    return this.rows.remove(key);
  }
  public Row getRow(String key) {
    return this.rows.get(key);
  }
}

public class Hallelulajah {

  Server server=null;
  public File dir=null;
  public Hallelulajah(String host, int port, String dir) {
    this.server=new Server(port,100,0xffee);
    this.dir=new File(dir);
    if (!this.dir.exists()) {
      if (!this.dir.mkdir()) {
        System.err.println("Fail : cannot create dir "+dir);
        System.exit(0);
      }
    } else if (!this.dir.isDirectory()) {
      System.err.println("Fail : "+dir+" exists but is not a directory");
      System.exit(0);
    }
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
    if (args.length != 3) {
      System.out.println("Usage: <listening host> <listening port> <directory>\ni.e. localhost 9001 db_dir");
      return;
    }
    Hallelulajah h=new Hallelulajah(args[0],Integer.parseInt(args[1]),args[2]);
    h.start();
  } catch(Exception e) {
    e.printStackTrace();
  }
  }
}
