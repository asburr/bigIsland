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
import java.util.Date;
import java.text.SimpleDateFormat;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;

// TODO make a pool of reusable JMRecord so GC is not so busy.
// TODO make a pool of LinkedList<JMRecord>, for the same reasons.
class JMRecord implements Comparable<JMRecord> {
  public long ts;
  public char cmd;
  public String key,data;
  public JMRecord(long ts,char cmd, String key, String data) {
    this.ts=ts; this.cmd=cmd; this.key=key; this.data=data;
  }
  public JMRecord(JMRecord o) {
    this.ts=o.ts; this.cmd=o.cmd; this.key=o.key; this.data=o.data;
  }
  @Override public int compareTo(JMRecord o) {
    long d=this.ts - o.ts;
    if (d<0) return -1;
    if (d>0) return 1;
    return 0;
  }
  public int compareTo(long ts) {
    long d=this.ts - ts;
    if (d<0) return -1;
    if (d>0) return 1;
    return 0;
  }
  @Override public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof JMRecord)) return false;
    return (this.compareTo((JMRecord)o)==0);
  }
   @Override public int hashCode() {
     return Objects.hash(getSigFields());     
   }
   private Object[] getSigFields() {
     Object[] result = { ts, cmd, key, data };
     return result;     
   }
}

class JournalM { // To Memory.
  LinkedList<JMRecord> m=new LinkedList<JMRecord>();
  public JournalM() { }

  boolean getting=false;
  long upto=0L;
  LinkedList<JMRecord> g=new LinkedList<JMRecord>();
  public void write(char cmd, String key, String row) {
    long ts=System.nanoTime();
    if (this.getting) this.getting();
    if (cmd!='B') this.m.add(new JMRecord(ts,cmd,key,row));
  }
  private void getting() {
    LinkedList<JMRecord> x=this.g;
    this.g=this.m;
    this.m=x; this.m.clear();
    JMRecord r=this.g.peekLast();
    while (r.compareTo(this.upto)>0) { // Last record newer than upto.
      r=this.g.removeLast();
      this.m.offerFirst(r); // Add newer journal event back to the head of the list.
      r=this.g.peekLast();
    }
    // Find table name in list.
    for (int i=this.g.size()-1;i>=0;i--) {
      r=this.g.get(i);
      if (r.cmd=='+' || r.cmd=='c') { // this is a table event, with the table name!
        this.m.offerFirst(new JMRecord(r)); // Duplicate the event to head of this journal list.
        break;
      }
    }
    this.getting=false;
  }
  public LinkedList<JMRecord> get(long until) {
    if (this.m.size()==0) return null;
    this.upto=until;
    this.getting=true;
    while (this.getting) try { Thread.sleep(10); } catch(Exception e) {}
    if (this.g.size()==0) return null;
    return this.g;
  }
  public void close() { // Make sure memory journalling has been written to disk before closing.
    while (this.m.size()>0) {
      if (this.getting) this.getting();
      try { Thread.sleep(50); } catch(Exception e) {}
    }
  }
  public void commit(Hallelulajah hall) { // Make sure memory journalling has been written to disk.
    while (this.m.size()>0) { // Journalling still in memory, wait for Hall to get it.
      if (this.getting) { this.getting(); break; }
      try { Thread.sleep(50); } catch(Exception e) {}
    }
    // If Hall is writing a commit to disk, wait for that to finish.
    while (!hall.committed) try { Thread.sleep(50); } catch(Exception e) {}
  }
}

class JournalO {
  private File journal=null;
  private RandomAccessFile j=null;
  public JournalO(File f,boolean append) {
    try {
      this.journal=f;
      this.j=new RandomAccessFile(this.journal,"rwd");
      // Append is the following seek!
      if (append) this.j.seek(this.j.length());
    } catch (FileNotFoundException e) {
      e.printStackTrace();
    }
  }
  private String empty="";
  public void write(char cmd, String key, String row) {
    try {
      this.j.writeLong(System.nanoTime());
      this.j.writeChar(cmd);
      this.j.writeUTF(key);
      if (row==null) this.j.writeUTF(this.empty);
      else this.j.writeUTF(row);
    } catch(Exception e) {
      e.printStackTrace();
      this.close();
    }
  }
  public long size() { return j.length(); }
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
  public String row=new String("");
  public boolean eof=false;
  public boolean next() {
    try {
      this.time=this.j.readLong();
      this.cmd=this.j.readChar();
      this.key=this.j.readUTF();
      this.row=this.j.readUTF();
      return true;
    } catch (EOFException e) {
      this.eof=true;
      return false;
    } catch (IOException e) {
      e.printStackTrace();
      this.eof=true;
      return false;
    }
  }
  // compare < 0, when this started before i
  // compare > 0, when this started after i
  // compare = 0, when this started at the same time at i.
  public long compare(JournalI i) {
    return this.time - i.time;
  }
}

class Yahweh implements Runnable {

  private Client client=null;
  private Hallelulajah hall=null;
  private JournalM j=null;
  public LinkedList<JMRecord> get(long until) { this.j.get(until); }

  public Yahweh(Client client,Hallelulajah hall) {
    this.client=client;
    this.hall=hall;
    this.j=new JournalM();
  }

  private Table table=null;
  private String row=null;
  private String key=null;
  public void run() {
    boolean journalledConnect=false;
    while (!this.client.shutdown) {
      if (!client.read(50,TimeUnit.MILLISECONDS)) {
        this.j.write('B',null,null); // Send blank event, to service any get of the journaling.
        continue;
      }
      String cmd=this.client.recvBuf_GetString(-1);
      if (cmd.length()==0) continue;
      String a[]=cmd.split(",",-1);
      switch (a[0].charAt(0)) {
      case 'x': {
        this.j.close();
        this.client.sendBuf_String("Success : exiting connection\n");
        return;
      }
      case 's': {
        this.j.commit(this.hall);
        this.client.sendBuf_String("Success : commits all changes to disk\n");
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
        journalledConnect=false;
        break;
      }
      case '+': { // Add table
        if (a.length != 2) { this.client.sendBuf_String("usage: +,<table name>\n"); continue; }
        this.table=hall.newTable(a[1]);
        this.client.sendBuf_String("Success : Table created or already exists with the name "+this.table.name+"\n");
        this.j.write('+',this.table.name,null);
        journalledConnect=false;
        break;
      }
      case '-': { // Delete table
        if (a.length != 1) { this.client.sendBuf_String("Usage : -\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : Please connect (c) to a table\n"); continue; }
        if (this.hall.backingUp) this.hall.d_addtable(this.table.name,this.table)
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
        this.row=cmd.substring(3+this.key.length());
        String r=this.table.addRow(this.key,this.row);
        if (r!=null) this.client.sendBuf_String("Fail : row exists already at this key\n");
        else {
          if (!journalledConnect) {
            journalledConnect=true;
            this.j.write('c',this.table.name,null);
          }
          this.j.write('a',this.key,this.row);
          this.client.sendBuf_String("Success : row added\n");
        }
        break;
      }
      case 'd': { // Delete row
        if (a.length != 2) { this.client.sendBuf_String("Usage : d,<key>\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect (c) to a table\n"); continue; }
        this.key=a[1];
        if (this.hall.backingUp) this.hall.d_addRow(this.table.name,this.row,this.table.getRow(this.key))
        this.row=this.table.delRow(this.key);
        if (this.row==null) { this.client.sendBuf_String("Fail : row does not exist\n"); continue; }
        if (!journalledConnect) {
          journalledConnect=true;
          this.j.write('c',this.table.name,null);
        }
        this.j.write('d',this.key,null);
        this.row=null;
        this.client.sendBuf_String("Success : deleted row at "+this.key+"\n");
        break;
      }
      case 'r': { // Replace row
        if (a.length != 3) { this.client.sendBuf_String("Usage : r,<key>,<data>\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect (c) to a table\n"); continue; }
        this.key=a[1];
        this.row=cmd.substring(3+this.key.length());
        String oldRow=this.table.replaceRow(this.key,this.row);
        if (oldRow==null) { this.client.sendBuf_String("Fail : row does not exist\n"); continue; }
        if (this.hall.backingUp) this.hall.d_addRow(this.table.name,this.row,oldRow);
        if (!journalledConnect) {
          journalledConnect=true;
          this.j.write('c',this.table.name,null);
        }
        this.j.write('r',this.key,this.row);
        this.client.sendBuf_String("Success : replace row at "+this.key+"\n");
        break;
      }
      case 'q': { // Query table
        if (a.length != 2) { this.client.sendBuf_String("Usage : q,<key>\n"); continue; }
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect to a table\n"); continue; }
        this.key=a[1];
        this.row=null;
        this.row=this.table.getRow(this.key);
        if (this.row!=null) this.client.sendBuf_String(this.row+"\n");
        else this.client.sendBuf_String("Fail : no such row\n");
        break;
      }
      default: {
        this.client.sendBuf_String("Usage: [x,c,+,-,a,d,q]\nDescription:"+
"\nx : exit :"+
"\nc,<table name> : connect to table : table must already exist"+
"\n+,<table name> : add table : no error when table already exists"+
"\n- : remove table : connect(c)"+
"\na,<key>,<data> : add row : connect(c)"+
"\nd,<key> : deletes row and returns row data : connect(c)"+
"\nq,<key> : return row data : connect(c)"+
"\n"
);
        break;
      }
    }
    }
  }
}

class Table {
  public String name=null;
  ConcurrentSkipListMap<String,String> rows=new ConcurrentSkipListMap<String,String>();
  public Table(String name) { this.name=name; }
  public String addRow(String key,String row) {
    return this.rows.putIfAbsent(key,new String(row));
  }
  public String delRow(String key) {
    return this.rows.remove(key);
  }
  public String replaceRow(String key,String row) {
    return this.rows.replace(key,row);
  }
  public String getRow(String key) {
    return this.rows.get(key);
  }
}

public class Hallelulajah {

  Server server=null;
  public long journalMaxSize=10000L;
  public File dir=null;
  public File backupFile=null;
  public File newBackupFile=null;
  public File journalFile=null;
  public JournalO j=null;
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
    JournalO j=new JournalO(this.journalFile,true);
    this.backupFile=new File(this.dir+File.separator+"Backup");
    this.newBackupFile=new File(this.dir+File.separator+"NewBackup");
    this.readFile(this.backupFile);
    this.journalFile=new File(this.dir+File.separator+"Journal");
    this.readFile(this.journalFile);
  }

  private void readFile(File f) {
    if (!f.exists()) return;
    JournalI i=new JournalI(f);
    Table table=null;
    while (i.next()) {
//System.err.println("Reading "+i.time+" cmd="+i.cmd+" key="+i.key+" data="+i.row);
      switch (i.cmd) {
      case 'c': { table=this.getTable(i.key); break; }
      case '+': { table=this.newTable(i.key); break; }
      case '-': { this.delTable(i.key,table); table=null; break; }
      case 'a': { table.addRow(i.key,i.row); break; }
      case 'd': { table.delRow(i.key); break; }
      default: { System.err.println("Fail : journal command "+i.cmd); return; }
      }
    }
  }

  LinkedList<Yahweh> jahs=new LinkedList<Yahweh>();
  public void start() {
    ExecutorService pool=Executors.newCachedThreadPool();
    while (true) {
      this.journal(); // Write JournalMs to file.
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

  public boolean committed=false;
  public void journal() {
    long until=System.nanoTime();
    this.committed=false;
    Set<JMRecord> s=new TreeSet<JMRecord>();
    for (Yahweh jah: this.jahs) {
      LinkedList<JMRecord> l=jah.get(until);
      if (l==null) continue;
      for (JMRecord r: l) s.add(r);
    }
    for (JMRecord r: s) this.j.write(r.cmd,r.key,r.data);
    this.committed=true;
    s.clear();
    if (this.j.size() > this.journalMaxSize) {
      this.mergeJournalWithBackup();
    }
  }
  ConcurrentSkipListMap<String,Table> dtables=new ConcurrentSkipListMap<String,Table>();
  boolean backingUp=false;
  private void mergeJournalWithBackup() {
    this.backingUp=true;
    this.j.close();
    this.j=new JournalO(this.newBackupFile,false);
    JournalI i=new JournalI(this.backupFile);
    this.backup(i);
    i=new JournalI(this.journalFile);
    this.backup(i);
    this.j.close();
    this.backingUp=false;
    this.dtables.clear();
    this.j=new JournalO(this.journalFile,false);
  }
  private void backup(JournalI i) {
    String tableName=null;
    boolean writeTable=true;
    while (i.next()) {
      switch (i.cmd) {
      case 'c':
      case '+':
        Table table=hall.getTable(a[1]);
        if (table!=null) {
          tableName=table.name;
          writeTable=false;
        } else {
          tableName=null;
          writeTable=false;
        }
        break;
      case 'r':
      case 'a':
        if (tableName!=null) {
          // Main database could be out of sync with the journal.
          // Query the deleted/changed database first and third.
          Table dtable=hall.getDTable(tableName);
          String row=this.dtable.getRow(i.key);
          if (row==null) row=this.table.getRow(i.key);
          if (row==null) row=this.dtable.getRow(i.key);
          if (row!=null) {
            if (writeTable) { this.j.write('c',tableName,null); writeTable=false; }
            this.j.write('r',i.key,row);
          }
        }
        break;
      }
    }
  }

  ConcurrentSkipListMap<String,Table> tables=new ConcurrentSkipListMap<String,Table>();
  public Table getDTable(String name) { return this.dtables.get(name); }
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
