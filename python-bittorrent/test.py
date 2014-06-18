import util
import bencode
import torrent
import tracker
from storage import Storage

info = torrent.make_info_dict('test');
storage = Storage(info)
storage.fillLocal()
print storage.getRest()