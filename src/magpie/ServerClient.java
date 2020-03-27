package magpie;

import java.nio.channels.*;

class ServerClient {

  AsynchronousSocketChannel client=null;
  ByteBuffer buf=null;

  public ServerClient(AsynchronousSocketChannel client,int bufferSize) {
    this.client=client;
    this.buf=ByteBuffer.allocate(buffersize);
  }

  public void close() {
    this.client.close();
    this.buf=null;
  }

}
