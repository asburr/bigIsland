package magpie;

/* MultiWordSearch is an algorithm to match multiple words with one pass
 * of the file being searched.
 *
 * Words are put into a character tree. Nodes of the tree are
 * kept in an active list to track which words are actively being
 * matched in the stream.
 *
 * Memory allocation
 * -----------------
 * Memory allocation occurs during the search when a match occurs. Matching
 * chars are copied from the tree and added to a String. The string is added
 * to a list of found strings.
 *
 * Memory usage
 * ------------
 * Each character requires a tree node, sub words like "hell" being a subword of "hello",
 * the subword is stored using the same nodes of the tree as he first part of "hello".
 *
 * A collapsing of the tree may reduce memory usage. The node holding a string of chars
 * to match would save on having nodes for each of the chars.
 */
import java.util.Comparator;
import java.util.Map;
import java.util.TreeMap;
import java.util.ArrayList;
import java.util.List;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.io.InputStreamReader;
import java.io.BufferedReader;
import java.io.InputStream;

class Word {
  public String s;
  public int i;
  public Word(String s) { this.s=s; this.i=0; }
  public char c;
  private boolean isMoreChar(int numChars) {
    return this.i+numChars <= this.s.length();
  }
  private void moreChar(int numChars) {
    if (this.i+numChars >= this.s.length()) {
      throw new RuntimeException("Expecting "+numChars+" more chars, only "+(this.s.length()-this.i));
    }
  }
  private char getChar() { return this.s.charAt(this.i++); }
  public boolean nextChar() {
    if (!this.isMoreChar(1)) return false;
    this.c=this.getChar();
    return true;
  }
}

class MultiWordNode {
  private char c='!';
  private MultiWordNode parent;
  private boolean endOfWord=false;
  public Map<Character,MultiWordNode> chars=null;
  public boolean hasNextNodes() {
    return this.chars!=null;
  }

  public MultiWordNode(MultiWordNode parent) { this.parent=parent; }
  public void print(String tab,boolean complete) {
    String newtab=tab;
    newtab+="node("+this.hashCode()+")";
    if (this.endOfWord) {
      System.out.println(newtab);
    }
    if (this.chars!=null) {
      for (char c: this.chars.keySet()) {
        MultiWordNode node=this.chars.get(c);
        newtab+="'"+node.c+"'";
        if (complete) node.print(newtab,complete);
        else System.out.println(newtab);
      }
    }
  }
  public void addWord(Word word) {
    if ( !word.nextChar() ) {
      this.endOfWord=true;
      return;
    }
    MultiWordNode n=null;
    if (this.chars==null) {
      this.chars=new TreeMap<Character,MultiWordNode>();
    }
    n=this.chars.get(word.c);
    if (n==null) {
      n=new MultiWordNode(this);
      n.c=word.c;
      this.chars.put(word.c,n);
    }
    n.addWord(word);
  }
  public void find(char c,List<String> found,
                    List<MultiWordNode> newActiveNodes
                  ) {
    MultiWordNode node=null;
    if (this.chars != null) {
      node=this.chars.get(c);
      if (node!=null) {
        if (node.endOfWord) {
          String f="";
          MultiWordNode n=node;
          while (n.parent != null) { f=n.c+f; n=n.parent; }
          found.add(f);
        }
        if (node.hasNextNodes()) {
          newActiveNodes.add(node);
        }
      }
    }
  }
}

public class MultiWordSearch {
  private List<MultiWordNode> activeNodes=new ArrayList<MultiWordNode>();
  private List<MultiWordNode> activeNodesNew=new ArrayList<MultiWordNode>();
  public MultiWordNode node=new MultiWordNode(null);
  public void addWord(Word word) { node.addWord(word); }
  public static boolean debug=false;
  public MultiWordSearch() {
    this.reset();
  }
  public void reset() {
    this.activeNodes.clear();
    this.activeNodes.add(this.node);
  }
  public void find(char c,List<String> found) {
    for (MultiWordNode node: this.activeNodes) {
      node.find(c,found,this.activeNodesNew);
    }
    this.activeNodes.clear();
    List<MultiWordNode> nodes=this.activeNodes;
    this.activeNodes=this.activeNodesNew;
    this.activeNodes.add(this.node);
    this.activeNodesNew=nodes;
    if (MultiWordSearch.debug) {
      int i=1,l=this.activeNodes.size();
      for (MultiWordNode node: this.activeNodes) {
        node.print("find at "+c+" "+(i++)+"/"+l+" active node=",false);
      }
    }
  }
  public void print() {
    this.node.print("",true);
  }
  public static void main(String[] args) {
    MultiWordSearch.debug=false;
   try {
    if (args.length != 2) {
      System.out.println("Usage: <text file, a word per line> <text file, to search>");
      return;
    }
    MultiWordSearch mws=new MultiWordSearch();
    Path file=Paths.get(args[0]);
    BufferedReader in=new BufferedReader(new InputStreamReader(Files.newInputStream(file)));
    String line;
    while ((line=in.readLine()) !=null ) { mws.addWord(new Word(line)); }
    in.close();
    mws.print();
    file=Paths.get(args[1]);
    in=new BufferedReader(new InputStreamReader(Files.newInputStream(file)));
    char c;
    List<String> found=new ArrayList<String>();
    int ln=1, ch=1,cin;
    while ((cin=in.read()) != -1) {
      c=(char)cin;
      if (c=='\n') {
        ln++; ch=1;
        mws.reset();
      } else {
        ch++;
        mws.find(c,found);
        for (String s: found) {
          System.out.println(s+" at "+ln+":"+(ch-s.length()));
        }
        found.clear();
      }
    }
    in.close();
   } catch (Exception e) {
     e.printStackTrace();
   }
  }
}
