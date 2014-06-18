import util
import bencode
import torrent
import tracker

tracker = tracker.Tracker(port = 8080,\
			inmemory = True, \
			interval = 10)
tracker.run()
