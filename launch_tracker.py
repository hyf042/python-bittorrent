import util
import bencode
import torrent
import tracker
from consts import consts

tracker = tracker.Tracker(port = consts['TRACKER_PORT'],\
			inmemory = True, \
			interval = 10)
tracker.run()
