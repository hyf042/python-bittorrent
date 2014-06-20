from twisted.internet import protocol, reactor
from connection import Connection
import struct

def integer_to_bytes(data):
	return struct.pack('B', data)
def bytes_to_integer(bytes):
	return struct.unpack('B', bytes)[0]
def validate_handshake(handshake, torrent):
	# compare the data besides peer_id
	if handshake[:-20] != torrent.handshake[:-20]
		return None
	return handshake[-20:]

class PeerProtocol(protocol.Protocol):
	def __init__(self, torrent):
		self.torrent = torrent
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

	def connectionMade(self):
		self.is_handshaked = False
		self.buffer = ''
		print len(self.torrent.handshake)
		# do handshake
		self.transport.write(self.torrent.handshake);
		

	def connectionLost(self, reason):
		self.connection.lost()
		self.torrent.lostConnection(self.connection)

	def dataReceived(self, data):
		self.buffer += data

		while True:
			if not self.is_handshaked:
				if len(self.buffer) >= len(self.torrent.handshake):
					handshake = self.buffer[:len(self.torrent.handshake)]
					
					print 'received handshake:', handshake, len(handshake)
					peer_id = validate_handshake(handshake, torrent):
					if peer_id == None:
						print 'handshake incorporate!'
						self.transport.loseConnection()
						return

					self._newConnection(peer_id)
					self.buffer = self.buffer[len(handshake):]	
				else:
					break
			elif not self.is_length_detected:
				if len(self.buffer) >= 4:
					self.message_length = struct.unpack('>I', self.buffer[:4])
					self.buffer = self.buffer[4:]

					if self.message_length == 0:
						self._heartbeat()
					else:
						self.is_length_detected = True
				else:
					break
			else:
				if len(self.buffer) >= self.message_length:
					data = self.buffer[:self.message_length]
					self.buffer = self.buffer[self.message_length:]

					self._parseCommand(data)
					self.is_length_detected = False
				else:
					break

	def breakup(self):
		self.transport.loseConnection()

	def _heartbeat(self):
		pass
	def _newConnection(self, peer_id):
		self.connection = Connection(self.torrent, peer_id)
		self.torrent.newConnection(self.connection)

		self.is_length_detected = False
		self.is_handshaked = True

	def _parseCommand(self, data):
		if len(data) == 0:
			return

		command = bytes_to_integer(data[:1])
		if command in self.parseFuncs:
			self.parseFuncs(data[1:])
		else:
			# no such command, breakup
			self.breakup()

	def _parseChoke(self, payload):
		pass
	def _parseUnchoke(self, payload):
		pass
	def _parseInterested(self, payload):
		pass
	def _parseUninterested(self, payload):
		pass
	def _parseHave(self, payload):
		pass
	def  _parseBitField(self, payload):
		pass
	def _parseRequest(self, payload):
		pass
	def _parsePiece(self, payload):
		pass
	def _parseCancel(self, payload):
		pass

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
		print "connection failed: ", reason
