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
import java.util.Map;
import java.util.TreeMap;
import java.util.Iterator;

// TODO make a pool of reusable JMRecord so GC is not so busy.
// TODO make a pool of LinkedList<JMRecord>, for the same reasons.
class JMRecord implements Comparable<JMRecord> {
  public long ts;
  public char cmd;
  public String key,data,tablename;
  public JMRecord(long ts,char cmd, String key, String data, String tablename) {
    this.ts=ts; this.cmd=cmd; this.key=key; this.data=data; this.tablename=tablename;
  }
  public JMRecord(JMRecord o) {
    this.ts=o.ts; this.cmd=o.cmd; this.key=o.key; this.data=o.data; this.tablename=o.tablename;
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

  boolean getting=false; // Hall calls get() which sets this, write() then gets the journals for Hall.
  public void write(char cmd, String key, String row, String tablename) {
    long ts=System.nanoTime();
    if (this.getting) this.getting();
    // Jah sends blank (B) commands every 50ms, the purpose being to look for any get requests from Hall.
    if (cmd!='B') this.m.add(new JMRecord(ts,cmd,key,row,tablename));
  }
  // g is the journals being passed back to Hall, see get().
  LinkedList<JMRecord> g=new LinkedList<JMRecord>();
  // upto is the timestamp that Hall sets before calling get(), to requesting journals upto the timestamp.
  long upto=0L;
  // getting() is called from ,tablenamewritei), to get the journals for Hall.
  private void getting() {
    this.g.clear(); // Swap g and m, first clear anything that remain in g.
    LinkedList<JMRecord> x=this.g; this.g=this.m; this.m=x; // Swap g and m.
    JMRecord r=this.g.peekLast(); // Newest journal.
    while (r.compareTo(this.upto)>0) { // journal newer than upto.
      r=this.g.removeLast(); // Dont pass newer journal to Hall.
      this.m.offerFirst(r); // Add journal back to the journaling.
      r=this.g.peekLast(); // Next newest journal.
    }
    // See if the journaling has the table name, otherwise copy it back into journalling.
    r=this.g.peekFirst();
    if (r==null || // Nothing in journalling, need table name in journalling.
        (r.cmd!='+' && r.cmd!='c')) // Last journal is not table name, need table name.
    { // Copy the table name back to the journalling.
      Iterator<JMRecord> i = this.g.descendingIterator(); 
      while (i.hasNext()) { 
        r=i.next(); 
        if (r.cmd=='+' || r.cmd=='c') { // this is a table event, with the table name!
          r=new JMRecord(r); // Duplicate the journal.
          r.cmd='c'; // Change journal type to connect (c).
          this.m.offerFirst(r); // Add journal to journalling.
          break;
        }
      }
    }
    this.getting=false;
  }
  // Hall calls get(), Hall blocks here until the Jah gets the journal.
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
      // Otherwise, no append, and truncate the file by setting the length.
      else this.j.setLength(0);
    } catch (Exception e) {
      e.printStackTrace();
    }
  }
  private String empty="";
  private String tablename=null;
  public void write(char cmd, String key, String row, String tablename) {
    try {
      if (this.tablename==null || !this.tablename.equals(tablename)) {
        this.tablename=tablename;
        this.j.writeChar('c');
        this.j.writeUTF(this.tablename);
        this.j.writeUTF(this.empty);
      }
      this.j.writeChar(cmd);
      this.j.writeUTF(key);
      if (row==null) this.j.writeUTF(this.empty);
      else this.j.writeUTF(row);
    } catch(Exception e) {
      e.printStackTrace();
      this.close();
    }
  }
  public long size() { try { return j.length(); } catch(Exception e) { e.printStackTrace(); return -1; } }
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
  public LinkedList<JMRecord> get(long until) { return this.j.get(until); }

  public Yahweh(Client client,Hallelulajah hall) {
    this.client=client;
    this.hall=hall;
    this.j=new JournalM();
  }

  private String tablename=null;
  private Table table=null;
  private Table d_table=null;
  private String row=null;
  private String key=null;
  private boolean parseKeyData(String cmd, String usage) {
    if (cmd.charAt(1) != ',') {
      this.client.sendBuf_String("fail : Usage : "+usage+"\n");
      return false;
    }
    int i=cmd.indexOf(',',2);
    if (i==-1 || cmd.length()<=i+1) {
      this.client.sendBuf_String("fail : usage : "+usage+"\n");
      return false;
    }
    this.key=cmd.substring(2,i);
    this.row=cmd.substring(i+1);
    return true;
  }
  private boolean parseKey(String cmd, String usage) {
    if (cmd.charAt(1) != ',' || cmd.length()<3) {
      this.client.sendBuf_String("fail : Usage : "+usage+"\n");
      return false;
    }
    this.key=cmd.substring(2);
    return true;
  }
  private boolean parseTable(String cmd, String usage) {
    if (cmd.charAt(1) != ',' || cmd.length() < 3) {
      this.client.sendBuf_String("Fail : Usage : "+usage+"\n");
      return false;
    }
    this.tablename=cmd.substring(2);
    return true;
  }
  public void run() {
    boolean human=true;
    while (!this.client.shutdown) {
      if (!client.read(50,TimeUnit.MILLISECONDS)) {
        this.j.write('B',null,null,null); // Send blank event, to service any get of the journaling by Hall.
        continue;
      }
      String cmd=this.client.recvBuf_GetString(-1);
      if (cmd.length()==0) continue;
      switch (cmd.charAt(0)) {
      case 'x': {
        this.j.close();
        if (human) this.client.sendBuf_String("Success : exiting connection\n");
        else this.client.sendBuf_String("");
        return;
      }
      case 'M': {
        human=false;
        this.client.sendBuf_String("");
        continue;
      }
      case 'H': {
        human=true;
        this.client.sendBuf_String("Hallelulajah\n");
        continue;
      }
      case 's': {
        this.j.commit(this.hall);
        if (human)
          this.client.sendBuf_String("Success : volatile changes are persistent\n");
        else
          this.client.sendBuf_String("");
        continue;
      }
      case 'c': { // Connect to table
        this.table=null;
        if (cmd.length()==1) {
          if (human) {
            if (this.table==null)
              this.client.sendBuf_String("Not connected to any table\n");
            else
              this.client.sendBuf_String("Connected to table name "+this.table.name+"\n");
          } else
            this.client.sendBuf_String(this.table.name);
          continue;
        }
        if (!this.parseTable(cmd,"t,<tablename>")) continue;
        this.table=hall.getTable(this.tablename);
        if (this.table==null)
          this.client.sendBuf_String("Fail : no such table "+this.tablename+"\n");
        else if (human)
          this.client.sendBuf_String("Success : connected to table name "+this.table.name+"\n");
        else
          this.client.sendBuf_String("");
        break;
      }
      case '+': { // Add table
        this.table=null;
        if (!this.parseTable(cmd,"+,<tablename>")) continue;
        this.table=hall.addTable(this.tablename);
        if (this.table==null)
          this.client.sendBuf_String("Fail : to add table "+this.tablename+"\n");
        else {
          if (human)
            this.client.sendBuf_String("Success : added table "+this.tablename+"\n");
          else
            this.client.sendBuf_String("");
          if (hall.backingUp) this.d_table=hall.d_addTable(this.tablename);
          this.j.write('+',this.tablename,null,this.tablename);
        }
        break;
      }
      case '-': { // Delete table
        if (cmd.length() > 1) {
          this.client.sendBuf_String("Fail : usage : -\n");
          continue;
        }
        if (this.table==null) {
          if (human)
            this.client.sendBuf_String("Fail : no table connected\n");
          else
            this.client.sendBuf_String("");
          continue;
        }
        if (!this.hall.delTable(this.table.name,this.table)) {
          if (human)
            this.client.sendBuf_String("Fail : Table does not exist could already be deleted "+this.table.name+"\n");
          else
            this.client.sendBuf_String("");
          this.table=null;
          continue;
        }
        this.j.write('-',this.table.name,null,null);
        if (human)
          this.client.sendBuf_String("Success : table "+this.table.name+" deleted\n");
        else
          this.client.sendBuf_String("");
        if (this.hall.backingUp) {
          this.hall.d_addTable(this.table.name);
          this.d_table=null;
        }
        this.table=null;
        break;
      }
      case 'a': { // Add row
        if (!this.parseKeyData(cmd,"a,<key>,<data>")) continue;
        if (this.table==null) {
          this.client.sendBuf_String("Fail : please connect (c) to a table\n");
          continue;
        }
        String r=this.table.addRow(this.key,this.row);
        if (r!=null) {
          this.client.sendBuf_String("Fail : row exists already at this key\n");
        } else {
          this.j.write('a',this.key,this.row,this.table.name);
          if (human)
            this.client.sendBuf_String("Success : row added\n");
          else
            this.client.sendBuf_String("");
          if (this.hall.backingUp) {
            if (this.d_table==null) this.d_table=hall.d_addTable(this.tablename);
            this.d_table.addRow(this.key,null); // Add null for a new row.
          }
        }
        break;
      }
      case 'd': { // Delete row
        if (!this.parseKey(cmd,"d,<key>")) continue;
        if (this.table==null) {
          this.client.sendBuf_String("Fail : please connect (c) to a table\n");
          continue;
        }
        this.row=this.table.delRow(this.key);
        if (this.row==null) {
          this.client.sendBuf_String("Fail : row does not exist\n");
          continue;
        }
        if (this.hall.backingUp) {
          if (this.d_table==null) this.d_table=hall.d_addTable(this.table.name);
          this.d_table.addRow(this.key,this.row);
        }
        this.j.write('d',this.key,null,this.table.name);
        this.row=null;
        if (human)
          this.client.sendBuf_String("Success : deleted row at "+this.key+"\n");
        break;
      }
      case 'r': { // Replace row
        this.parseKeyData(cmd,"r,<key>,<data>");
        if (this.table==null) {
          this.client.sendBuf_String("Fail : please connect (c) to a table\n");
          continue;
        }
        String oldRow=this.table.replaceRow(this.key,this.row);
        if (oldRow==null) {
          this.client.sendBuf_String("Fail : row does not exist\n");
          continue;
        }
        if (this.hall.backingUp) {
          if (this.d_table==null) this.d_table=hall.d_addTable(this.table.name);
          this.d_table.addRow(this.key,oldRow);
        }
        this.j.write('r',this.key,this.row,this.table.name);
        if (human)
          this.client.sendBuf_String("Success : replace row at "+this.key+"\n");
        else
          this.client.sendBuf_String("");
        break;
      }
      case 'q': { // Query table
        this.parseKey(cmd,"q,<key>");
        if (this.table==null) { this.client.sendBuf_String("Fail : please connect to a table\n"); continue; }
        this.row=this.table.getRow(this.key);
        if (human) {
          if (this.row!=null) this.client.sendBuf_String(this.row+"\n");
          else this.client.sendBuf_String("Fail : no such row\n");
        } else {
          if (this.row!=null) this.client.sendBuf_String(this.row);
          else this.client.sendBuf_String("");
        }
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
  // Add the row, or replaces existing row.
  public void addXRow(String key,String row) {
    this.rows.put(key,new String(row));
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
  public File oldBackupFile=null;
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
    this.journalFile=new File(this.dir+File.separator+"Journal");
    this.j=new JournalO(this.journalFile,true);
    this.backupFile=new File(this.dir+File.separator+"Backup");
    this.newBackupFile=new File(this.dir+File.separator+"NewBackup");
    this.oldBackupFile=new File(this.dir+File.separator+"OldBackup");
    this.readFile(this.backupFile);
    this.readFile(this.journalFile);
  }

  private void readFile(File f) {
    if (!f.exists()) return;
    JournalI i=new JournalI(f);
    Table table=null;
    while (i.next()) {
      switch (i.cmd) {
      case 'c': { table=this.addTable(i.key); break; }
      case '+': { table=this.addTable(i.key); break; }
      case '-': { this.delTable(i.key,table); table=null; break; }
      case 'a': { table.addRow(i.key,i.row); break; }
      case 'd': { table.delRow(i.key); break; }
      case 'r': { table.addXRow(i.key,i.row); break; }
      default: { System.err.println("Fail : journal command "+i.cmd); return; }
      }
    }
  }

  LinkedList<Yahweh> jahs=new LinkedList<Yahweh>();
  public void start() {
    ExecutorService pool=Executors.newCachedThreadPool();
    long before=System.currentTimeMillis();
    while (true) {
      long after=System.currentTimeMillis();
      if ((after-before) > 150) {
        before=after;
        this.journal(); // Write JournalMs to file.
      }
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

  // committed implements the save(s) command.
  public boolean committed=false;
  private Map<Long,LinkedList<JMRecord>> jmap=new TreeMap<Long,LinkedList<JMRecord>>();
  // journal() writes journals to file which is also the save(s) command.
  private void listforeach(LinkedList<JMRecord> l) {
    for (JMRecord r: l)
      this.j.write(r.cmd,r.key,r.data,r.tablename);
  }
  // Write Jah memory journals to file.
  public void journal() {
    long until=System.nanoTime();
    this.committed=false;
    for (Yahweh jah: this.jahs) {
      LinkedList<JMRecord> l=jah.get(until);
      if (l==null) continue;
      for (JMRecord r: l) {
        LinkedList<JMRecord> ls=this.jmap.get(r.ts);
        if (ls==null) { ls=new LinkedList<JMRecord>(); this.jmap.put(r.ts,ls); }
        ls.add(r);
      }
    }
    this.jmap.forEach((k, v) -> this.listforeach(v));
    this.committed=true; // For the save(s) command.
    if (this.j.size()>0) {
      this.jmap.clear();
      this.mergeJournalWithBackup();
    }
  }
  // dtables holds original key/data pairs when backup in progress and key/data pair was changed.
  ConcurrentSkipListMap<String,Table> dtables=new ConcurrentSkipListMap<String,Table>();
  // backingUp is true when backup is in progress.
  boolean backingUp=false;
  // mergeJournalWithBackup() - creates a new backup file from the old backup and the journal file.
  private void mergeJournalWithBackup() {
    this.backingUp=true;
    this.j.close();
    this.j=new JournalO(this.newBackupFile,false);
    JournalI i=null;
    if (this.backupFile.exists()) {
      i=new JournalI(this.backupFile);
      this.backup(i);
    }
    i=new JournalI(this.journalFile);
    this.backup(i);
    this.j.close();
    this.backingUp=false;
    this.dtables.clear();
    this.j=new JournalO(this.journalFile,false);
    // Move Backup to OldBackup.
    if (this.backupFile.exists()) {
      this.oldBackupFile.delete();
      this.backupFile.renameTo(this.oldBackupFile);
    }
    // Move NewBackup to Backup
    this.newBackupFile.renameTo(this.backupFile);
  }
  // Select which journal commands to write to file.
  private void backup(JournalI i) {
    String tableName=null;
    Table table=null;
    while (i.next()) {
      switch (i.cmd) {
      case 'c':
      case '+':
        tableName=i.key;
        table=this.getTable(tableName);
        if (table==null) tableName=null;
        break;
      case 'r':
      case 'a':
        if (tableName!=null) {
          String row=null;
          // Query dtable for original value that has changed during the backup.
          Table dtable=this.d_getTable(tableName);
          if (dtable!=null) row=dtable.getRow(i.key);
          if (row==null) {
            // Query table for the value.
            row=table.getRow(i.key);
            // Query again dtable, use this value if we now find it.
            dtable=this.d_getTable(tableName);
            if (dtable!=null) { String x=dtable.getRow(i.key); if (x!=null) row=x; }
          }
          if (row!=null) {
            this.j.write('r',i.key,row,tableName);
          }
        }
        break;
      }
    }
  }

  ConcurrentSkipListMap<String,Table> tables=new ConcurrentSkipListMap<String,Table>();
  public Table d_getTable(String name) { return this.dtables.get(name); }
  public Table getTable(String name) { return this.tables.get(name); }
  public Table addTable(String name) {
    Table n=new Table(name);
    Table t=this.tables.putIfAbsent(name,n);
    if (t!=null) return t;
    return n;
  }
  public Table d_addTable(String tablename) {
    return this.tables.putIfAbsent(tablename,null);
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
