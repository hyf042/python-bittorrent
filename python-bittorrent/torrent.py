# torrent.py
# Torrent file related utilities

from hashlib import md5, sha1
from random import choice
import socket
from struct import pack, unpack
from threading import Thread
from time import sleep, time
import types
import traceback
from urllib import urlencode, urlopen
from util import collapse, slice

import network
from bencode import decode, encode
from twisted.internet import protocol, reactor
from consts import consts

CLIENT_NAME = consts['CLIENT_NAME']
CLIENT_ID = consts['CLIENT_ID']
CLIENT_VERSION = consts['CLIENT_VERSION']
PEER_PORT = consts['PEER_PORT']

def make_info_dict(file):
	""" Returns the info dictionary for a torrent file. """

	with open(file) as f:
		contents = f.read()

	piece_length = consts['PIECE_LENGTH']	# TODO: This should change dependent on file size

	info = {}

	info["piece length"] = piece_length
	info["length"] = len(contents)
	info["name"] = file
	info["md5sum"] = md5(contents).hexdigest()

	# Generate the pieces
	pieces = slice(contents, piece_length)
	pieces = [ sha1(p).digest() for p in pieces ]
	info["pieces"] = collapse(pieces)

	return info

def make_torrent_file(file = None, tracker = None, comment = None):
	""" Returns the bencoded contents of a torrent file. """

	if not file:
		raise TypeError("make_torrent_file requires at least one file, non given.")
	if not tracker:
		raise TypeError("make_torrent_file requires at least one tracker, non given.")

	torrent = {}

	# We only have one tracker, so that's the announce
	if type(tracker) != list:
		torrent["announce"] = tracker
	# Multiple trackers, first is announce, and all go in announce-list
	elif type(tracker) == list:
		torrent["announce"] = tracker[0]
		# And for some reason, each needs its own list
		torrent["announce-list"] = [[t] for t in tracker]

	torrent["creation date"] = int(time())
	torrent["created by"] = CLIENT_NAME
	if comment:
		torrent["comment"] = comment

	torrent["info"] = make_info_dict(file)

	return encode(torrent)

def write_torrent_file(torrent = None, file = None, tracker = None, \
	comment = None):
	""" Largely the same as make_torrent_file(), except write the file
	to the file named in torrent. """

	if not torrent:
		raise TypeError("write_torrent_file() requires a torrent filename to write to.")

	data = make_torrent_file(file = file, tracker = tracker, \
		comment = comment)
	with open(torrent, "w") as torrent_file:
		torrent_file.write(data)

def read_torrent_file(torrent_file):
	""" Given a .torrent file, returns its decoded contents. """

	with open(torrent_file) as file:
		return decode(file.read())

def generate_peer_id():
	""" Returns a 20-byte peer id. """

	# As Azureus style seems most popular, we'll be using that.
	# Generate a 12 character long string of random numbers.
	random_string = ""
	while len(random_string) != 12:
		random_string = random_string + choice("1234567890")

	return "-" + CLIENT_ID + CLIENT_VERSION + "-" + random_string

def make_tracker_request(info, peer_id, tracker_url, event = 'started', peer_port = PEER_PORT):
	""" Given a torrent info, and tracker_url, returns the tracker
	response. """

	# Generate a tracker GET request.
	payload = {"info_hash" : info,
			"peer_id" : peer_id,
			"port" : peer_port,
			"uploaded" : 0,
			"downloaded" : 0,
			"left" : 1000,
			"event": event,
			"compact" : 1}
	payload = urlencode(payload)

	# Send the request
	response = urlopen(tracker_url + "?" + payload).read()

	return decode(response)

def decode_expanded_peers(peers):
	""" Return a list of IPs and ports, given an expanded list of peers,
	from a tracker response. """

	return [(p["ip"], p["port"]) for p in peers]

def decode_binary_peers(peers):
	""" Return a list of IPs and ports, given a binary list of peers,
	from a tracker response. """

	peers = slice(peers, 6)	# Cut the response at the end of every peer
	return [(socket.inet_ntoa(p[:4]), decode_port(p[4:])) for p in peers]

def get_peers(peers):
	""" Dispatches peer list to decode binary or expanded peer list. """

	if type(peers) == str:
		return decode_binary_peers(peers)
	elif type(peers) == list:
		return decode_expanded_peers(peers)

def decode_port(port):
	""" Given a big-endian encoded port, returns the numerical port. """

	return unpack(">H", port)[0]

def generate_handshake(info_hash, peer_id):
	""" Returns a handshake. """

	protocol_id = "BitTorrent protocol"
	len_id = len(protocol_id)
	reserved = "00000000"

	return network.integer_to_bytes(len_id) + protocol_id + reserved + info_hash + peer_id

def send_recv_handshake(handshake, host, port):
	""" Sends a handshake, returns the data we get back. """

	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((host, port))
	s.send(handshake)

	data = s.recv(len(handshake))
	s.close()

	return data

class PeerError(Exception):
	""" Raised if an error occurs in peer. """

	def __init__(self, msg):
		self.msg = msg

	def __str__(self):
		""" Pretty-prints the information. """

		return self.msg

class Torrent():
	def __init__(self, torrent_file, port = PEER_PORT,
		error_handler = None, tracker_retry_time = consts['TRACKER_RETRY_TIME']):
		self.running = False
		self.downloading = False

		self.peer_port = port
		self.error_handler = error_handler
		self.tracker_retry_time = tracker_retry_time

		self.data = read_torrent_file(torrent_file)

		self.info_hash = sha1(encode(self.data["info"])).digest()
		self.peer_id = generate_peer_id()
		self.handshake = generate_handshake(self.info_hash, self.peer_id)

	def handleError(self, err):
		print 'Error: ' + err + '\n\t' + traceback.format_exc()
		if self.error_handler != None:
			self.error_handler(err)

	def run(self):
		""" Start the torrent running. """

		try:
			if not self.running:
				self.running = True

				# run in main thread
				#self.tracker_loop = Thread(target = self.perform_tracker_request, \
				#	args = (self.data["announce"], self.info_hash, self.peer_id))
				#self.tracker_loop.start()
				self._perform_tracker_request(self.data["announce"], self.info_hash, self.peer_id)		
				self._perform_mainLoop()
				self._cleanup(self.data["announce"], self.info_hash, self.peer_id)

		except Exception as e:
			self.handleError(repr(e))

	def stop(self):
		""" Stop the torrent from running. """
		if self.running:
			self.running = False
			
			if self.downloading:
				self.downloading = False
				reactor.stop()

			#self.tracker_loop.join()

	################################
	# Interface
	################################
	def newConnection(self, connection):
		self.connections[connection.peer_id] = connection
	def lostConnection(self, connection):
		if connection.peer_id not in self.connections:
			del self.connections[connection.peer_id]

	def _perform_mainLoop(self):
		""" Run torrent main logic """
		self.downloading = True
		self.connections = {}

		for peer_info in self.peers:
			reactor.connectTCP(peer_info[0], peer_info[1], network.BTPeerClientFactory(self))

		reactor.listenTCP(self.peer_port, network.BTPeerServerFactory(self))

		reactor.run()

	def _perform_tracker_request(self, url, info_hash, peer_id):
		""" Make a tracker request to url, every interval seconds, using
		the info_hash and peer_id, and decode the peers on a good response. """

		cnt = 0
		while self.running and cnt < self.tracker_retry_time:
			self.tracker_response = make_tracker_request(info_hash, peer_id, url, 
				peer_port = self.peer_port)

			if "failure reason" not in self.tracker_response:
				self.peers = get_peers(self.tracker_response["peers"])
				print self.peers
				return

			sleep(self.tracker_response["interval"])

		raise Exception('can not connect to tracker!')

	def _cleanup(self, url, info_hash, peer_id):
		self.tracker_response = make_tracker_request(info_hash, peer_id, url, 
				event = 'stopped', peer_port = self.peer_port)

		if "failure reason" not in self.tracker_response:
			print 'exit successfully'
			return
