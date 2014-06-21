import random
import time

class PiecePicker:
	def __init__(self, torrent):
		self.torrent = torrent
		self.storage = torrent.storage

		self.piece_num = torrent.piece_num

	def _getRarePieces(self):
		if self.torrent.paused:
			return

		pieces_count = [0]*self.piece_num
		pieces_sorted = []
		for connection in self.torrent.connections.values():
			for piece in xrange(0, self.piece_num):
				if connection.hasPiece(piece):
					pieces_count[piece] += 1
		for piece in xrange(0, self.piece_num):
			pieces_sorted.append( (pieces_count[piece] + random.random(), piece) )

		def comparator(a, b):
			if a[0] < b[0]:
				return -1
			elif a[0] > b[0]:
				return 1
			else:
				return 0
		pieces_sorted.sort(comparator)
		return [term[1] for term in pieces_sorted]

	def nextRequests(self, count = 1):
		if self.torrent.paused:
			return

		# get usable connections
		connections = self.torrent.getUsableConnections()
		random.shuffle(connections)

		# get pieces in rare order
		pieces_in_rare_order = self._getRarePieces()

		# get blocks of uncompleted pieces as first order
		blocks_in_order = self.storage.gen_priority_list(count << 1)
		# get other blocks sorted in rarest as second order
		for piece_index in pieces_in_rare_order:
			flag = False
			for connection in connections:
				if connection.hasPiece(piece_index):
					flag = True
					break
			if flag:
				blocks_in_order.extend(self.storage.gen_uncompleted_blocks(piece_index))
				if len(blocks_in_order) > (count << 3):
					break

		# remove the blocks already in downloading
		for request in self.torrent.downloading:
			if request[1] in blocks_in_order:
				blocks_in_order.remove(request[1])

		# get #count number of request
		next_blocks = []
		
		# connections = self.torrent.getUnchokedConnections()
		# random.shuffle(connections)
		# print 'usable:', [conn.peer_id for conn in connections]

		# while True:
		# 	flag = False # has one acceppted

		# 	for connection in connections:
		# 		for block in blocks_in_order:
		# 			piece_index = block[0]

		# 			if connection.hasPiece(piece_index):
		# 				next_blocks.append( (connection, block) )
		# 				blocks_in_order.remove(block)

		# 				if len(next_blocks) >= count:
		# 					return next_blocks

		# 				flag = True
		# 				break
		# 	if not flag:
		# 		break			

		
		print 'usable:', [conn.peer_id for conn in connections]

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


