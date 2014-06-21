import util
import bencode
import torrent
import tracker
import sys
from storage import Storage

t = torrent.Torrent(sys.argv[1], target_file = sys.argv[2], port = int(sys.argv[3]))
t.run()