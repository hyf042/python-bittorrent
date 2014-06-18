from simpledb import Database
from torrent import PeerError

class Storage():
	block_size = 16*1024
	def __init__(self, info):
		self.piece_length = info["piece length"]
		self.length = info["length"]

		self.info = info
		self.piece_num = (self.length + self.piece_length - 1) / self.piece_length
		self.db = Database(None)#info["name"] + '.tmp'
		self.completed = bytearray(self.piece_num);
		self.full = False

		self.validate()

	def validate(self):
		count = 0
		for i in range(self.piece_num):
			if i in self.db:
				self.completed[i] = len(self.db[i]) >= self.getPieceSize(i);
			else:
				self.completed[i] = False
			count += self.completed[i]
			
		self.full = count >= self.piece_num


	def fillLocal(self):
		with open(self.info["name"]) as f:
			contents = f.read()

		if len(contents) != self.length:
			raise PeerError("file length incompatible");
		for i in range(self.piece_num):
			start_pos = i*self.piece_length
			end_pos = (i+1)*self.piece_length

			if end_pos >= self.length:
				self.push(i, 0, contents[start_pos:])
			else:
				self.push(i, 0, contents[start_pos: end_pos])

		self.full = True

	def getBlockIndex(self, block_offset):
		return block_offset % Storage.block_size

	def getPieceSize(self, piece_index):
		if piece_index < self.piece_num-1:
			return self.piece_length;
		else:
			return self.length - (self.piece_num-1) * self.piece_length;

	def push(self, piece_index, block_offset, data):
		if self.full:
			return
		if piece_index >= self.piece_num or piece_index < 0:
			raise PeerError("piece_index out of range");

		piece_buffer = ""
		if piece_index in self.db:
			piece_buffer = self.db[piece_index]

		if block_offset != len(piece_buffer):
			raise PeerError("block_offset is not continuous");

		piece_buffer += data;

		if len(data) > self.getPieceSize(piece_index):
			raise PeerError("piece size is out of range");

		self.db[piece_index] = piece_buffer
		self.completed[piece_index] = True

	def getOffset(self, piece_index):
		if piece_index >= self.piece_num or piece_index < 0:
			raise PeerError("piece_index out of range");

		if piece_index not in self.db:
			return 0
		else:
			return len(self.db[piece_index])

	def getRest(self):
		return [index for index, val in enumerate(self.completed) if not self.completed[index]];

	def isComplete(self, piece_index):
		if piece_index >= self.piece_num or piece_index < 0:
			raise PeerError("piece_index out of range");

		return self.completed[piece_index]>0
