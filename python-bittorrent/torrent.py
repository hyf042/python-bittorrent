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

from network import BTPeerServerFactory, BTPeerClientFactory
from bencode import decode, encode
from twisted.internet import protocol, reactor, task
from piece_picker import PiecePicker
from peer_selector import PeerSelector
from bitarray import BitArray
from storage import Storage
from consts import consts

CLIENT_NAME = consts['CLIENT_NAME']
CLIENT_ID = consts['CLIENT_ID']
CLIENT_VERSION = consts['CLIENT_VERSION']
PEER_PORT = consts['PEER_PORT']

def make_info_dict(file):
	""" Returns the info dictionary for a torrent file. """

	with open(file, 'rb') as f:
		contents = f.read()

	piece_length = consts['PIECE_LENGTH']	# TODO: This should change dependent on file size

	info = {}

	info["piece length"] = piece_length
	info["length"] = len(contents)
	info["name"] = file
	info["md5sum"] = md5(contents).hexdigest()

	# Generate the pieces
	pieces = slice(contents, piece_length)
	print file, 'length:', len(contents), 'piece_num:', len(pieces)
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
	with open(torrent, "wb") as torrent_file:
		torrent_file.write(data)

def read_torrent_file(torrent_file):
	""" Given a .torrent file, returns its decoded contents. """

	with open(torrent_file, 'rb') as file:
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

	return pack('B', len_id) + protocol_id + reserved + info_hash + peer_id

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
	def __init__(self, torrent_file, target_file, port = PEER_PORT,
		error_handler = None, tracker_retry_time = consts['TRACKER_RETRY_TIME']):
		self.running = False
		self.is_downloading = False
		self.completed = False
		self.paused = False

		self.peer_port = port
		self.error_handler = error_handler
		self.tracker_retry_time = tracker_retry_time

		self.data = read_torrent_file(torrent_file)

		self.info_hash = sha1(encode(self.data["info"])).digest()
		self.peer_id = generate_peer_id()
		self.handshake = generate_handshake(self.info_hash, self.peer_id)

		self.tracker_thread = None

		# check is seed
		self.target_file = target_file
		self.storage = Storage(self.data['info'])
		self.piece_num = self.storage.piece_num
		print 'piece_num:', self.piece_num
		import os
		if os.path.exists(target_file):
			self.storage.set_file(target_file)

		self.picker = PiecePicker(self)
		self.selector = PeerSelector(self)
		self.downloading = []

	def __del__(self):
		""" Stop the tracker thread. """
		if self.tracker_thread != None:
			self.tracker_loop.join()
		
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
			
			if self.is_downloading:
				self.is_downloading = False
				reactor.stop()

				self._cleanup(self.data["announce"], self.info_hash, self.peer_id)

			if self.tracker_thread != None:
				self.tracker_loop.join()

	def pause(self, paused = True):
		if self.paused == paused:
			return
		self.paused = paused
		if paused:
			# choke all
			for connection in self.torrent.connections.values():
				connection.choke()

	################################
	# Interface
	################################
	def newConnection(self, connection):
		self.connections[connection.peer_id] = connection
		print '[Torrent]\ttotal connected peers: ', len(self.connections)
		connection.bitfield(self.storage.gen_complete_str())
		

	def lostConnection(self, connection):
		if connection.peer_id in self.connections:
			del self.connections[connection.peer_id]
		self._cleanup_connection(connection)
		print '[Torrent]\ttotal connected peers: ', len(self.connections)
	################################
	# Event
	################################
	def onRequest(self, connection, block_info):
		if self.paused:
			return
		data = self.storage.get(*block_info)
		connection.piece(block_info, data)

	def onPiece(self, connection, block_info, block_data):
		if self.paused:
			return
		print 'push piece', block_info, len(block_data)
		self.storage.push(block_info[0], block_info[1], block_data)
		if self.storage.is_piece_received(block_info[0]):
			self.pushHave(block_info[0])

			if self.storage.is_all_piece_received():
				# save target file
				self.storage.save_target_file(self.target_file)

				self.onComplete()

		request = (connection, block_info)
		self.downloading.remove(request)
		self._try_download()

	def onCancel(self, connection, block_info):
		# now nothing to do
		pass

	def onUnchoked(self, connection):
		self._try_download()

	def onComplete(self):
		print '[Torrent]\tDownload Completed!'
		self.completed = True

		# inform the tracker
		self.tracker_thread = Thread(target = self._inform_tracker_completed, \
			args = (self.data["announce"], self.info_hash, self.peer_id))
		self.tracker_thread.start()

	def pushHave(self, piece_index):
		for connection in self.connections.values():
			connection.have(piece_index)

	################################
	# Util
	################################
	def checkBlockInfo(self, block_info):
		if block_info[0] not in range(0, self.piece_num):
			return False
		return True	
	def getUsableConnections(self):
		ret = []
		for connection in self.connections.values():
			if not connection.is_choked and connection.peer_id not in self.downloading:
				ret.append(connection)
		return ret
	def hasPiece(self, piece_index):
		return self.storage.is_piece_received(piece_index)
	def isSeed(self):
		return self.completed

	################################
	# Privates
	################################
	def _perform_mainLoop(self):
		""" Run torrent main logic """
		self.is_downloading = True
		self.connections = {}

		for peer_info in self.peers:
			reactor.connectTCP(peer_info[0], peer_info[1], BTPeerClientFactory(self))
		self._launch_timer()
		reactor.listenTCP(self.peer_port, BTPeerServerFactory(self))

		if self.storage.is_all_piece_received():
			self.onComplete()
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
				print '[Torrent]\tpeers:', self.peers
				return

			sleep(self.tracker_response["interval"])

		raise Exception('can not connect to tracker!')

	def _inform_tracker_completed(self, url, info_hash, peer_id):
		try:
			self.tracker_response = make_tracker_request(info_hash, peer_id, url, 
				event = 'completed', peer_port = self.peer_port)
			if "failure reason" not in self.tracker_response:
				print '[Torrent]\tinform tracker completed.'
		except Exception, e:
			pass

	def _cleanup(self, url, info_hash, peer_id):
		self.tracker_response = make_tracker_request(info_hash, peer_id, url, 
				event = 'stopped', peer_port = self.peer_port)

		self._remove_timer()
		if "failure reason" not in self.tracker_response:
			print 'exit successfully'
			return

	def _cleanup_connection(self, connection):
		newList = []
		for request in self.downloading:
			if (request[0] != connection):
				newList.append(request)
		self.downloading = newList

		self._try_download()

	def _try_download(self):
		if len(self.downloading) >= consts['PEER_DOWNLOAD_LIMIT']:
			return

		idle_cnt = consts['PEER_DOWNLOAD_LIMIT'] - len(self.downloading)
		if idle_cnt > 0:
			requests = self.picker.nextRequests(idle_cnt)
			for request in requests:
				self._do_request(request)

	def _do_request(self, request):
		connection = request[0]
		block_info = request[1]

		if connection in self.downloading:
			return;
		self.downloading.append(request)
		connection.request(block_info)

	def _launch_timer(self):
		self.select_best = task.LoopingCall(self.selector.selectBest)
		self.select_optimistically = task.LoopingCall(self.selector.selectOptimistically)
		self.select_best.start(consts['SELECT_BEST_PEERS_TIME'])
		self.select_optimistically.start(consts['SELECT_OPTIMISTICALLY_TIME'])

	def _remove_timer(self):
		try:
			self.select_best.stop()
			self.select_optimistically.stop()
		except Exception,e:
			pass

