import torrent
import sys

file = sys.argv[1]
torrent_path = sys.argv[2]
if len(sys.argv) > 3:
	tracker = sys.argv[3]
else:
	tracker = "http://127.0.0.1:8080"

torrent.write_torrent_file(torrent_path, file, tracker)