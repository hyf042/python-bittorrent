# connection.py
# The Connection

import socket
from torrent import *
from bencode import decode, encode

class Connection():
	def __init__(self, address):
		self.running = False

		self.handshaked = False
		self.is_choke = True
		self.is_interested = False

		self.address

	def run(self):
		""" start the peer task """

		if not self.running:
			self.running = True

			self.peer_thread = Thread(target = self.peer_thread, \
				args = (self.peer))
			self.peer_thread.start()

	def peer_thread(self, ip, port):
		self.s = socket.socket()
		s.bind(address)

