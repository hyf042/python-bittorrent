import util
import bencode
import torrent
import tracker
import sys
from storage import Storage

t = torrent.Torrent("test.torrent", int(sys.argv[1]))
t.run()