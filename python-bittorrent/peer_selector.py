from consts import consts
import random

class PeerSelector:
	def __init__(self, torrent):
		self.torrent = torrent
		self.luckyman = None
		self.stable_group = []
		self.MAX_UNCHOKED_PEER = consts['MAX_UNCHOKED_PEER']

	def selectBest(self):
		connections = self.torrent.connections.values()
		for connection in connections:
			connection.resetMeasurement()

		candidates = [connection for connection in connections if connection != self.luckyman and connection.is_interested]

		if self.torrent.isSeed():
			candidates.sort(lambda a,b : b.getUploadRate() - a.getUploadRate())
		else:
			candidates.sort(lambda a,b : b.getDownloadRate() - a.getDownloadRate())

		# pick best peers
		self.stable_group = candidates[: self.MAX_UNCHOKED_PEER]
		self._resetChokes()

		print '[PeerSelector]\tdo select best:', [con.peer_id for con in self.stable_group]

	def selectOptimistically(self):
		candidates = [connection for connection in self.torrent.connections.values() if connection not in self.stable_group and connection.is_interested]
		if len(candidates) > 0:
			self.luckyman = random.choice(candidates)
		else:
			self.luckyman = None
		self._resetChokes()

		if self.luckyman != None:
			print '[PeerSelector]\tdo select optimistically', self.luckyman.peer_id
		else:
			print '[PeerSelector]\tdo select optimistically', 'None'

	def _resetChokes(self):
		for connection in self.torrent.connections.values():
			if connection not in self.stable_group and self.luckyman != connection:
				connection.choke()
			else:
				connection.unchoke()
