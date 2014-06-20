import torrent
import sys

torrent_path = sys.argv[1]
file = sys.argv[2]
tracker = "http://127.0.0.1:8080"

torrent.write_torrent_file(torrent_path, file, tracker)