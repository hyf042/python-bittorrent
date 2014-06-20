from consts import consts
import random

class PeerSelector:
	def __init__(self, torrent):
		self.luckyman = None
		self.stable_group = []
		self.MAX_UNCHOKED_PEER = consts['MAX_UNCHOKED_PEER']

	def selectBest(self):
		print 'do select best'

		for connection in self.torrent.connections:
			connection.resetMeasurement()

		candidates = [connection for connection in self.torrent.connections if connection != self.luckyman and connection.is_interested]
		candidates.sort(lambda a,b : b.getDownloadRate() - a.getDownloadRate())

		# pick best peers
		self.stable_group = candidates[: self.MAX_UNCHOKED_PEER]
		self._resetChokes()

	def selectOptimistically(self):
		print 'do select optimistically'

		candidates = [connection for connection in self.torrent.connections if connection not in self.stable_group]
		if len(candidates) > 0:
			self.luckyman = random.choice(candidates)
		else:
			self.luckyman = None
		self._resetChokes()

	def _resetChokes(self):
		for connection in self.torrent.connections:
			if connection not in self.stable_group and self.luckyman != connection:
				connection.unchoked()
			else:
				connection.choked()
