from twisted.internet import protocol, reactor
from connection import Connection
from consts import consts
import struct
import time

def validate_handshake(handshake, torrent):
	# compare the data besides peer_id
	if handshake[:-20] != torrent.handshake[:-20]:
		return None
	return handshake[-20:]

class PeerProtocol(protocol.Protocol):
	def __init__(self, torrent):
		self.torrent = torrent
		self.connection = None
		self.parseFuncs = {
			0:	self._parseChoke,
			1:	self._parseUnchoke,
			2:	self._parseInterested,
			3:	self._parseUninterested,
			4:	self._parseHave,
			5:	self._parseBitField,
			6:	self._parseRequest,
			7:	self._parsePiece,
			8:	self._parseCancel
		}
		self.command_str = {
			0:	'#choke#',
			1:	'#unchoke#',
			2:	'#interested#',
			3:	'#uninterested#',
			4:	'#have#',
			5:	'#bitfield#',
			6:	'#request#',
			7:	'#piece#',
			8:	'#cancel#'
		}
		self.downloadBytes = 0
		self.uploadBytes = 0
		self.startMeasureTime = time.time()

	def connectionMade(self):
		self.is_handshaked = False
		self.buffer = ''
		# do handshake
		self.transport.write(self.torrent.handshake)
		

	def connectionLost(self, reason):
		if self.connection != None:
			self.connection.lost()

	def dataReceived(self, data):
		self.downloadBytes += len(data)
		self.buffer += data
		#print '[Network]\tReceived data! length:', len(data)

		while True:
			if not self.is_handshaked:
				if len(self.buffer) >= len(self.torrent.handshake):
					handshake = self.buffer[:len(self.torrent.handshake)]
					
					print '[Network]\treceived handshake:', handshake, len(handshake)
					peer_id = validate_handshake(handshake, self.torrent)
					if peer_id == None:
						print 'handshake incorporate!'
						self.transport.loseConnection()
						return

					self._newConnection(peer_id)
					self.buffer = self.buffer[len(handshake):]	
				else:
					break
			elif not self.is_length_detected:
				#print 'length detect', len(self.buffer)
				if len(self.buffer) >= 4:
					self.message_length = struct.unpack('>I', self.buffer[:4])[0]
					self.buffer = self.buffer[4:]

					if self.message_length == 0:
						self._heartbeat()
					else:
						self.is_length_detected = True
				else:
					break
			else:
				#print 'content detect', len(self.buffer), self.message_length
				if len(self.buffer) >= self.message_length:
					data = self.buffer[:self.message_length]
					self.buffer = self.buffer[self.message_length:]

					self._parseCommand(data)
					self.is_length_detected = False
				else:
					break

	def breakup(self):
		self.transport.loseConnection()

	def getDownloadRate(self):
		if self.downloadBytes == 0:
			return 0
		else:
			return self.downloadBytes / (time.time() - self.startMeasureTime)
	def getUploadRate(self):
		if self.uploadBytes == 0:
			return 0
		else:
			return self.uploadBytes / (time.time() - self.startMeasureTime)
	def resetMeasurement(self):
		self.startMeasureTime = time.time()
		self.downloadBytes = 0
		self.uploadBytes = 0

	def _newConnection(self, peer_id):
		self.connection = Connection(peer_id, self, self.torrent)
		self.torrent.newConnection(self.connection)

		self.is_length_detected = False
		self.is_handshaked = True

	#################################
	# send command
	#################################
	def sendHeartbeat(self):
		self.transport.write(struct.pack('>I', 0))
	def sendChoke(self):
		self._sendMessage(0)
	def sendUnchoke(self):
		self._sendMessage(1)
	def sendInterested(self):
		self._sendMessage(2)
	def sendUninterested(self):
		self._sendMessage(3)
	def sendHave(self, piece_index):
		self._sendMessage(4, struct.pack('>I', piece_index))
	def sendBitfield(self, bitfield_s):
		self._sendMessage(5, bitfield_s)
	def sendRequest(self, piece_index, block_offset, block_length):
		data = struct.pack('>I', piece_index) + struct.pack('>I', block_offset) + struct.pack('>I', block_length)
		self._sendMessage(6, data)
	def sendPiece(self, piece_index, block_offset, block_data):
		# do measurement
		self.uploadBytes += len(block_data)
		
		data = struct.pack('>I', piece_index) + struct.pack('>I', block_offset) + block_data
		self._sendMessage(7, data)
	def sendCancel(self, piece_index, block_offset, block_length):
		data = struct.pack('>I', piece_index) + struct.pack('>I', block_offset) + struct.pack('>I', block_length)
		self._sendMessage(8, data)

	def _sendMessage(self, command, payload = ''):
		data = struct.pack('>I', 1+len(payload))  + struct.pack('B', command)[0] + payload
		print '[Network]\tsend message', self.command_str[command], ', length:', len(data), 'to', self.connection.peer_id
		self.transport.write(data)

	#################################
	# parse command
	#################################
	def _parseCommand(self, data):
		#print 'parse command', len(data)

		if len(data) == 0:
			return

		command = struct.unpack('B', data[:1])[0]
		if command in self.parseFuncs:
			print '[Network]\treceived message', self.command_str[command], len(data), 'by', self.connection.peer_id
			self.parseFuncs[command](data[1:])
		else:
			# no such command, breakup
			self.breakup()

	def _heartbeat(self):
		pass
	def _parseChoke(self, payload):
		self.connection.chokeBy()
	def _parseUnchoke(self, payload):
		self.connection.unchokeBy()
	def _parseInterested(self, payload):
		self.connection.interestedBy()
	def _parseUninterested(self, payload):
		self.connection.uninterestedBy()
	def _parseHave(self, payload):
		if len(payload) != 4:
			self.breakup()
			return
		piece_index = struct.unpack('>I', payload[:4])[0]
		self.connection.haveBy(piece_index)
	def  _parseBitField(self, payload):
		self.connection.bitfieldBy(payload)
	def _parseRequest(self, payload):
		if len(payload) != 12:
			self.breakup()
			return
		piece_index = struct.unpack('>I', payload[:4])[0]
		block_offset = struct.unpack('>I', payload[4:8])[0]
		block_length = struct.unpack('>I', payload[8:])[0]
		self.connection.requestBy(piece_index, block_offset, block_length)
	def _parsePiece(self, payload):
		if len(payload) < 8:
			self.breakup()
			return
		piece_index = struct.unpack('>I', payload[:4])[0]
		block_offset = struct.unpack('>I', payload[4:8])[0]
		block_data = payload[8:]
		self.connection.pieceBy(piece_index, block_offset, block_data)
	def _parseCancel(self, payload):
		if len(payload) != 12:
			self.breakup()
			return
		piece_index = struct.unpack('>I', payload[:4])[0]
		block_offset = struct.unpack('>I', payload[4:8])[0]
		block_length = struct.unpack('>I', payload[8:])[0]
		self.connection.cancelBy(piece_index, block_offset, block_length)

class BTPeerServerFactory(protocol.Factory):
	def __init__(self, torrent):
		self.torrent = torrent
	def buildProtocol(self, addr):
		return PeerProtocol(self.torrent)

class BTPeerClientFactory(protocol.ClientFactory):
	def __init__(self, torrent):
		self.torrent = torrent

	def buildProtocol(self, addr):
		return PeerProtocol(self.torrent)

	def clientConnectionFailed(self, connector, reason):
		print "[Network]\tconnection failed: ", reason
