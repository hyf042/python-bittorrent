import random

class PiecePicker:
	def __init__(self, torrent):
		self.torrent = torrent
		self.storage = torrent.storage

		self.piece_num = len(torrent.data['info']['pieces'])

	def _getRarePieces(self):
		pieces_count = [0]*self.piece_num
		pieces_sorted = []
		for connection in self.torrents.connections:
			for piece in xrange(0, pieces_count):
				if connection.hasPiece(piece):
					pieces_count[piece]++
		for piece in xrange(0, pieces_count):
			pieces_sorted.append( (pieces_count[piece] + random.random(), piece) )
		pieces_sorted.sort(lambda a,b : a[0]-b[0])
		return [term[1] for term in pieces_sorted]

	def nextRequests(self, count = 1):
		pieces_in_rare_order = self._getRarePieces()

		# get blocks of uncompleted pieces as first order
		blocks_in_order = self.storage.getUncompletedBlocks()
		# get other blocks sorted in rarest as second order
		for piece_index in pieces_in_rare_order:
			blocks_in_order.extend(self.storage.getBlocks(piece_index))
		# remove the blocks already in downloading
		for request in self.torrent.downloading:
			if request[1] in blocks_in_order:
				blocks_in_order.remove(request[1])

		# get #count number of request
		next_blocks = []
		connections = self.torrent.getUsableConnections()
		for block in blocks_in_order:
			piece_index = block[0]

			best_choice = None
			maxDownloadRate = 0
			for connection in connections:
				if connection.hasPiece(piece_index) and (best_choice == None or connection.getDownloadRate() > maxDownloadRate):
					best_choice = connection
					maxDownloadRate = connection.getDownloadRate()
			if best_choice != None:
				next_blocks.append( (best_choice, block) )
				connections.remove(best_choice)
			if len(next_blocks) >= count:
				break

		return next_blocks


