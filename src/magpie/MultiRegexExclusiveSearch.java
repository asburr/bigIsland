package magpie;

/* MultiRegexExclusiveSearch
 * 
 * A stream processing regex search algorith.
 *
 * Regex are put into a static tree. This exclusive algorithm
 * consumes all chars that match the char range beyond any occurence
 * range, excluding more than one match on the same range of chars.
 *
 * Regex supported are,
 *  [s-e] - range of chars, start (s) to end(e) char.
 *  {Dec: s,e } - restrict the matched range to the number range, start (s) to end(e) decimal int.
 *  {Occ: s,e } - Repeat the range match, minimum start (s) range to end (e).
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

class CharacterRange implements Comparator<CharacterRange>,Comparable<CharacterRange> {
  public char first,last;
  public CharacterRange(char first,char last) {
    this.first=first;
    this.last=last;
  }
  public boolean in(int i) {
    if (i < this.first) return false;
    if (i > this.last) return false;
    return true;
  }
  public int compareTo(CharacterRange o) {
    if (this.first < o.first) return -1;
    if (this.last > o.last) return 1;
    return 0;
  }
  public int compare(CharacterRange o1,CharacterRange o2) {
    return o1.compareTo(o2);
  }
}

class NegCharacterRange implements Comparator<NegCharacterRange>,Comparable<NegCharacterRange> {
  public char first,last;
  public NegCharacterRange(char first,char last) {
    this.first=first;
    this.last=last;
  }
  public boolean in(int i) {
    if (i < this.first) return true;
    if (i > this.last) return true;
    return false;
  }
  public int compareTo(NegCharacterRange o) {
    if (this.first < o.first || this.last > o.last) return 0;
    int f=this.first-o.first;
    int l=this.last-o.last;
    if (f > l) return -1;
    return 1;
  }
  public int compare(NegCharacterRange o1,NegCharacterRange o2) {
    return o1.compareTo(o2);
  }
}

class MinMax {
  public int min,max;
  public MinMax(int min, int max) {
    this.min=min;
    this.max=max;
  }
  public boolean inRange(int i) {
    return ( i >= this.min && i <= this.max);
  }
  public boolean belowMax(int i) {
    return (i < this.max);
  }
  public boolean aboveMin(int i) {
    return (i >= this.min);
  }
}

class Word {
  public String s;
  public int i;
  public boolean endOfWord=false;
  public Word(String s) {
    this.s=s;
    this.i=0;
    this.endOfWord=!this.isMoreChar(1);
  }
  public ArrayList<CharacterRange> rs=new ArrayList<CharacterRange>();
  public ArrayList<NegCharacterRange> nrs=new ArrayList<NegCharacterRange>();
  public char c;
  public MinMax occ;
  public MinMax num;
  public boolean beginningOfLine=false,endOfLine=false;
  private boolean isMoreChar(int numChars) {
    return this.i+numChars <= this.s.length();
  }
  private void moreChar(int numChars) {
    if (this.i+numChars >= this.s.length()) {
      throw new RuntimeException("Expecting "+numChars+" more chars, only "+(this.s.length()-this.i)+" at "+this.i+" in "+this.s+" c="+this.c);
    }
  }
  private char getChar() {
    char c=this.s.charAt(this.i++);
    return c;
  }
  private int getInt(char upto) {
    String x="";
    this.moreChar(2);
    this.c=this.getChar();
    while (this.c != upto) {
      x+=this.c;
      if (this.c < '0' || this.c > '9') {
        throw new RuntimeException("Expecting digit or "+upto+" but got "+this.c+" at "+this.i+" in "+this.s);
      }
      this.moreChar(1);
      this.c=this.getChar();
    }
    return Integer.parseInt(x);
  }
  // Range should leave a character in this.c that is not a bracket and is
  // either a char (when no range) or start of control ({).
  public boolean Range() {
    if ( this.c != '[' ) return false;
    char charStart=this.getChar();
    boolean negated=false;
    if (charStart == '^') {
      negated=true;
      charStart=this.getChar();
    }
    char dash=this.getChar();
    char charEnd=this.getChar();
    char closeBracket=this.getChar();
    if (dash != '-') throw new RuntimeException("Expecting dash and got charStart="+charStart+" dash="+dash+" charEnd="+charEnd+" at "+this.i+" in "+this.s);
    if (closeBracket == 'B') {
      closeBracket=this.getChar();
      this.beginningOfLine=true;
    } else if (closeBracket == 'E') {
      closeBracket=this.getChar();
      this.endOfLine=true;
    }
    if (closeBracket != ']') {
      throw new RuntimeException("Expecting close bracket and got "+closeBracket+" at "+this.i+" in "+this.s);
    }
    if (!negated) {
      this.rs.add(new CharacterRange(charStart,charEnd));
    } else {
      this.nrs.add(new NegCharacterRange(charStart,charEnd));
    }
    this.c=this.getChar();
    return true;
  }
  public void Control() {
    if ( this.c != '{' ) {
      throw new RuntimeException("Missing control structure at "+this.i+" in "+this.s);
    }
    this.c=this.getChar();
    while (this.c != '}') {
      char c1=this.c;
      char c2=this.getChar();
      char c3=this.getChar();
      char colon=this.getChar();
      if (c1=='O' && c2=='c' && c3=='c' && colon==':') {
        this.occ=new MinMax(this.getInt(','),this.getInt(' '));
      } else if (c1=='D' && c2=='e' && c3=='c' && colon==':') {
        this.num=new MinMax(this.getInt(','),this.getInt(' '));
      } else if (c1=='H' && c2=='e' && c3=='c' && colon==':') {
        this.num=new MinMax(this.getInt(','),this.getInt(' '));
      } else {
        throw new RuntimeException("Unknown control "+c1+c2+c3+colon+" expecting Occ: or Dec: or Hex: at "+this.i+" in "+this.s);
      }
      this.c=this.getChar();
    }
  }
  public void nextChar() {
    this.occ=null;
    this.num=null;
    this.rs.clear();
    this.nrs.clear();
    if (!this.isMoreChar(1)) {
      this.endOfWord=true;
      return;
    }
    this.c=this.getChar();
    if (this.Range()) {
      while (this.Range());
      this.Control();
    }
    if (!this.isMoreChar(1)) {
      this.endOfWord=true;
    }
  }
}

class MultiRegexNode {
  public boolean reactivate=false; // Node is to be reactivated for the next match.
  public boolean active=false; // Node is currently active.
  public char parentChar='!';
  public String nodeChars=null; // For repeating nodes.
  public MultiRegexNode parent;
  public boolean endOfWord=false; // this node matches a word.
  public Map<Character,MultiRegexNode> chars=null; // Next node on char.
  public Map<CharacterRange,MultiRegexNode> ranges=null; // Next node on range of char.
  public Map<NegCharacterRange,MultiRegexNode> nranges=null; // Next node on range of char.
  public ArrayList<MultiRegexNode> bol=null,eol=null;
  public boolean hasNextNodes() {
    return (this.chars!=null || this.ranges!=null || this.nranges!=null || this.occ!=null);
  }
  public MinMax occ=null;
  public MinMax num=null;

  public MultiRegexNode(MultiRegexNode parent) {
    this.parent=parent;
  }
  public void print(String tab,boolean complete) {
    String newtab=tab;
    if (MultiRegexExclusiveSearch.debug) {
      newtab+=" node("+this.hashCode();
      if (this.nodeChars != null) {
        newtab+=" nchars="+this.nodeChars;
      }
    }
/*
 else if (this.parent != null) {
      newtab+=" pchar="+this.parentChar;
    }
*/
    if (this.occ!=null || this.num!=null) {
      newtab+="{";
      if (this.occ!=null) {
        newtab+="Occ:"+this.occ.min+"-"+this.occ.max+" ";
      }
      if (this.num!=null) {
        newtab+="Dec:"+this.num.min+"-"+this.num.max+" ";
      }
      newtab+="}";
    }
    if (this.endOfWord) {
      if (MultiRegexExclusiveSearch.debug) newtab+=")";
      System.out.println(newtab);
    }
    if (this.chars!=null) {
      for (char c: this.chars.keySet()) {
        MultiRegexNode node=this.chars.get(c);
        if (MultiRegexExclusiveSearch.debug) {
          if (complete) node.print(newtab+" char="+c+")",complete);
          else System.out.println(newtab+" char="+c+")");
        } else {
          if (complete) node.print(newtab+" char="+c,complete);
          else System.out.println(newtab+" char="+c);
        }
      }
    }
    if (this.ranges!=null) {
      for (CharacterRange r: this.ranges.keySet()) {
        CharacterRange nr=new CharacterRange(r.first,r.last);
        MultiRegexNode node=this.ranges.get(nr);
        String n=newtab+"["+r.first+"-"+r.last+"]";
        if (MultiRegexExclusiveSearch.debug) n+=")";
        if (complete) node.print(n,complete);
        else System.out.println(n);
      }
    }
    if (this.nranges!=null) {
      for (NegCharacterRange r: this.nranges.keySet()) {
        NegCharacterRange nr=new NegCharacterRange(r.first,r.last);
        nr.first++; nr.last++;
        MultiRegexNode node=this.nranges.get(nr);
        String n=newtab+"[^"+r.first+"-"+r.last+"]";
        if (MultiRegexExclusiveSearch.debug) newtab+=")";
        if (complete) node.print(n,complete);
        else System.out.println(n);
      }
    }
  }
  public CharacterRange cr=new CharacterRange('0','0');
  public NegCharacterRange ncr=new NegCharacterRange('0','0');
  public void addWord(Word word) {
    word.nextChar();
    MultiRegexNode nn=new MultiRegexNode(this);
    nn.endOfWord=word.endOfWord;
    nn.num=word.num;
    nn.occ=word.occ;
    if (nn.occ!=null) nn.nodeChars="";
    if (word.rs.size() > 0) {
      if (this.ranges==null) {
        this.ranges=new TreeMap<CharacterRange,MultiRegexNode>();
      }
      for (CharacterRange r:word.rs) {
        MultiRegexNode n=this.ranges.get(r);
        if (n!=null) throw new RuntimeException("Duplicate regex pattern");
        this.ranges.put(r,nn);
      }
    }
    if (word.nrs.size() > 0) {
      if (this.nranges==null) {
        this.nranges=new TreeMap<NegCharacterRange,MultiRegexNode>();
      }
      for (NegCharacterRange nr:word.nrs) {
        MultiRegexNode n=this.nranges.get(nr);
        if (n!=null) throw new RuntimeException("Duplicate regex pattern");
        this.nranges.put(nr,nn);
      }
    }
    if (word.nrs.size() == 0 && word.rs.size() == 0) {
      if (this.chars==null) {
        this.chars=new TreeMap<Character,MultiRegexNode>();
      }
      MultiRegexNode n=this.chars.get(word.c);
      if (n!=null) throw new RuntimeException("Duplicate regex pattern");
      nn.parentChar=word.c;
      this.chars.put(word.c,nn);
    } else {
      word.nrs.clear();
      word.rs.clear();
    }
    if (word.beginningOfLine) {
      if (this.bol==null) this.bol=new ArrayList<MultiRegexNode>();
      this.bol.add(nn);
    }
    if (word.endOfLine) {
      if (this.eol==null) this.eol=new ArrayList<MultiRegexNode>();
      this.eol.add(nn);
    }
    if (!nn.endOfWord) nn.addWord(word);
  }
  public void getFound(List<String> found) {
    if (!this.endOfWord) return;
    found.add(this.get(""));
  }
  private String get(String v) {
    if (this.parent == null) return v;
    if (this.nodeChars!=null) v=this.nodeChars+v;
    else v=this.parentChar+v;
    return this.parent.get(v);
  }
  public MultiRegexNode findNode(char c) {
    MultiRegexNode node=null;
    if (this.chars != null) {
      node=this.chars.get(c);
      if (node!=null) return node;
    }
    if (this.ranges != null) {
      this.cr.first=this.cr.last=c;
      node=this.ranges.get(this.cr);
      if (node!=null) return node;
    }
    if (this.nranges != null) {
      this.ncr.first=this.ncr.last=c;
      node=this.nranges.get(this.ncr);
      if (node!=null) return node;
    }
    return null;
  }
  public void deactivate() {
    MultiRegexNode node=this;
    while (node != null ) {
      node.active=false;
      node.reactivate=false;
      node=node.parent;
    }
  }
  public void findBOL(List<String> found,
                    List<MultiRegexNode> newActiveNodes,
                    List<MultiRegexNode> idle
                  ) {
    if (this.bol!=null) {
      for (MultiRegexNode n: this.bol) newActiveNodes.add(n);
    }
  }
  public void findEOL(List<String> found,
                    List<MultiRegexNode> newActiveNodes,
                    List<MultiRegexNode> idle
                  ) {
    if (this.eol!=null) {
      for (MultiRegexNode n: this.eol) newActiveNodes.add(n);
    }
  }
  public void find(char c,List<String> found,
                    List<MultiRegexNode> newActiveNodes,
                    List<MultiRegexNode> idle
                  ) {
    if (MultiRegexExclusiveSearch.debug) System.out.println("find start node="+this.hashCode()+" c="+c+" nodeChars="+nodeChars);
    if (this.nodeChars!=null) { // occ
      if (MultiRegexExclusiveSearch.debug) System.out.println("find nodeChars node="+this.hashCode()+" c="+c);
      if (this.parent!=null) {
        MultiRegexNode n=this.parent.findNode(c);
        if (n==null) {
          if (MultiRegexExclusiveSearch.debug) System.out.println("find nodeChars parent not found c="+c);
        } else {
          if (MultiRegexExclusiveSearch.debug) System.out.println("find nodeChars parent found node="+n.hashCode()+" c="+c);
        }
        if (n==this) {
          if (this.nodeChars.length() < this.occ.max) {
            this.reactivate=true;
            newActiveNodes.add(this);
            this.nodeChars=this.nodeChars+c;
            return;
          } else {
            if (MultiRegexExclusiveSearch.debug) System.out.println("find too many chars chars="+this.nodeChars);
          }
        } else {
          if (this.nodeChars.length() < this.occ.min) {
            if (MultiRegexExclusiveSearch.debug) System.out.println("find too few chars chars="+this.nodeChars);
            return;
          }
        }
        if (this.num!=null) {
          try {
            if (!this.num.inRange(Integer.parseInt(this.nodeChars))) {
              if (MultiRegexExclusiveSearch.debug) System.out.println("out of num range num="+this.nodeChars+" node="+this.hashCode());
              return;
            }
          } catch(Exception ignore) {
            if (MultiRegexExclusiveSearch.debug) System.out.println("bad number num="+this.nodeChars+" node="+this.hashCode());
            return;
          }
        }
      }
    }
    this.getFound(found);

    MultiRegexNode node=this.findNode(c);
    if (node!=null) {
      if (MultiRegexExclusiveSearch.debug) System.out.println("node="+this.hashCode()+" found="+node.hashCode()+" for="+c);
      if (node.nodeChars!=null) {
        if (node.active) {
          if (MultiRegexExclusiveSearch.debug) System.out.println("node already active "+node.hashCode());
          return;
        }
        node.nodeChars=""+c;
        if (MultiRegexExclusiveSearch.debug) System.out.println("find 1 node="+this.hashCode()+" active node="+node.hashCode());
        node.reactivate=true;
        newActiveNodes.add(node);
        return;
      }
      if (node.hasNextNodes()) {
        if (MultiRegexExclusiveSearch.debug) System.out.println("find 2 node="+this.hashCode()+" active node="+node.hashCode());
        node.reactivate=true;
        newActiveNodes.add(node);
        return;
      }
      node.getFound(found);
    }
    if (MultiRegexExclusiveSearch.debug) System.out.println("find 3 idle node="+this.hashCode());
    idle.add(this);
    return;
  }
}

public class MultiRegexExclusiveSearch {
  private List<MultiRegexNode> activeNodes=new ArrayList<MultiRegexNode>();
  private List<MultiRegexNode> activeNodesNew=new ArrayList<MultiRegexNode>();
  private List<MultiRegexNode> idle=new ArrayList<MultiRegexNode>();
  public MultiRegexNode node;
  public void addWord(Word word) { this.node.addWord(word); }
  public static boolean debug=false;
  public MultiRegexExclusiveSearch() {
    this.node=new MultiRegexNode(null);
    this.reset();
  }
  public void reset() {
    this.activeNodes.clear();
  }
  public void findBOL(List<String> found) {
    for (MultiRegexNode node: this.activeNodes) {
      node.findBOL(found,this.activeNodesNew,this.idle);
    }
    for (MultiRegexNode node: this.idle) {
      node.deactivate();
    }
    this.node.findBOL(found,this.activeNodesNew,this.idle);
    this.findEND(found);
  }
  public void findEOL(List<String> found) {
    for (MultiRegexNode node: this.activeNodes) {
      node.findEOL(found,this.activeNodesNew,this.idle);
    }
    for (MultiRegexNode node: this.idle) {
      node.deactivate();
    }
    this.node.findEOL(found,this.activeNodesNew,this.idle);
    this.findEND(found);
  }
  public void find(char c,List<String> found) {
    this.findStart();
    for (MultiRegexNode node: this.activeNodes) {
      node.find(c,found,this.activeNodesNew,this.idle);
    }
    this.node.find(c,found,this.activeNodesNew,this.idle);
    this.findEND(found);
  }
  public void findStart() {
    for (MultiRegexNode node: this.activeNodes) node.reactivate=false;
  }
  private void findEND(List<String> found) {
    for (MultiRegexNode node: this.idle) {
      if (!node.reactivate) {
        if (MultiRegexExclusiveSearch.debug) System.out.println("idle node="+node.hashCode()+" done");
        node.deactivate();
      }
    }
    this.idle.clear();
    this.activeNodes.clear();
    for (MultiRegexNode node: this.activeNodesNew) {
      node.active=true;
      this.activeNodes.add(node);
    }
    this.activeNodesNew.clear();
/*
    if (MultiRegexExclusiveSearch.debug) {
      for (MultiRegexNode n: this.activeNodes) {
        n.print(c+":",false);
      }
    }
*/
  }
  public void print() {
    this.node.print("",true);
  }
  public static void main(String[] args) {
   try {
    if (args.length < 2) {
      System.out.println("Usage: <text file, a word per line> <text file, to search> <debugon");
      return;
    }
    if (args.length == 3) {
      MultiRegexExclusiveSearch.debug=args[2].equals("debugon");
    }
    MultiRegexExclusiveSearch mws=new MultiRegexExclusiveSearch();
    Path file=Paths.get(args[0]);
    BufferedReader in=new BufferedReader(new InputStreamReader(Files.newInputStream(file)));
    String line;
    int lineNum=0;
    try {
      while ((line=in.readLine()) !=null ) { lineNum++; mws.addWord(new Word(line)); }
    } catch (Exception e) {
      System.err.println(e.getMessage()+" at "+args[0]+":"+lineNum);
      return;
    }
    in.close();
    mws.print();
    file=Paths.get(args[1]);
    in=new BufferedReader(new InputStreamReader(Files.newInputStream(file)));
    char c;
    List<String> found=new ArrayList<String>();
    int ln=1, ch=0,cin;
    mws.reset();
    boolean newline=false;
    while ((cin=in.read()) != -1) {
      c=(char)cin;
      if (newline) {
        newline=false; ln++; ch=0;
      }
      if (c=='\n') {
        newline=true;
      }
      ch++;
      mws.find(c,found);
      for (String s: found) {
        System.out.println("FOUND "+s+" at "+ln+":"+(ch-(s.length()-1)));
      }
      found.clear();
    }
    in.close();
   } catch (Exception e) {
     e.printStackTrace();
   }
  }
}
