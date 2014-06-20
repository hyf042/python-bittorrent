# connection.py
# The Connection

import socket
from torrent import *
from bencode import decode, encode

class Connection():
	def __init__(self, torrent, peer_id):
		self.running = False

		self.is_choked = True
		self.is_interested = False

		self.torrent = torrent
		self.peer_id = peer_id

	def lost(self):
		print self.peer_id, 'lost'



