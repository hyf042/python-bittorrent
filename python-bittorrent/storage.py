from simpledb import Database
from hashlib import md5, sha1
from consts import consts
from util import slice
import struct

class Storage:
	block_size = consts['BLOCK_LENGTH']

	def __init__(self, info):
		self.info = info

		self.piece_length = info["piece length"]
		self.length = info["length"]
		self.piece_num = (self.length - 1) / self.piece_length + 1
		self.data_db = Database(None)
		self.comp_db = Database(None)
		self.sha1 = slice(info["pieces"], 20)
		self.downloaded_size = 0

	def set_file(self, filename):
		with open(filename, 'rb') as f:
			contents = f.read()

		if md5(contents).hexdigest() != self.info["md5sum"]:
			# if check failed, just work as no file at all
			print '[Storage] warnning, Md5 check failed.'
			return


		for i in xrange(self.piece_num):
			for j in xrange(self.get_block_num_in_piece(i)):
				start_pos = i * self.piece_length + j * Storage.block_size
				end_pos = start_pos + self.get_block_size(i, j)
				self.push(i, j * Storage.block_size, contents[start_pos: end_pos])

		self.downloaded_size = len(contents)

		return contents

	def is_file_info_legal(self, piece_index, offset, length):
		if piece_index >= self.piece_num:
			return False
		if not self.is_offset_legal(offset):
			return False
		if offset + length > self.get_piece_size(piece_index):
			return False
		return True

	def is_offset_legal(self, offset):
		return offset % Storage.block_size == 0

	def get_block_size(self, piece_index, block_index):
		if (piece_index < self.piece_num -1) or (block_index < self.get_block_num_in_piece(piece_index) - 1):
			return Storage.block_size
		return self.get_piece_size(piece_index) - (self.get_block_num_in_piece(piece_index) - 1) * Storage.block_size

	def get_offset_index(self, offset):
		return offset / Storage.block_size

	def get_block_offset_from_index(self, index):
		return Storage.block_size * index

	def get_piece_size(self, piece_index):
		if piece_index < self.piece_num - 1:
			return self.piece_length
		return self.length - (self.piece_num - 1) * self.piece_length

	def get_block_num_in_piece(self, piece_index):
		return (self.get_piece_size(piece_index) - 1) / Storage.block_size + 1

	def get(self, piece_index, offset, length):
		# ignore length
		block_index = self.get_offset_index(offset)
		db_index = str(piece_index) + "_" + str(block_index)
		if not db_index in self.data_db:
			return
		return self.data_db[db_index]
	def get_piece(self, piece_index):
		ret = ""
		for i in xrange(self.get_block_num_in_piece(piece_index)):
			ret += self.get(piece_index, self.get_block_offset_from_index(i), Storage.block_size)
		return ret

	def validate_piece(self, piece_index):
		num = self.get_block_num_in_piece(piece_index)
		if num!= self.comp_db[piece_index]:
			return False
		ret = self.get_piece(piece_index)
		if sha1(ret).digest() != self.sha1[piece_index]:
			return False
		return True

	def push(self, piece_index, offset, data):
		if piece_index >= self.piece_num:
			return
		if not self.is_offset_legal(offset):
			return
		block_index = self.get_offset_index(offset)
		db_index = str(piece_index) + "_" + str(block_index)
		if db_index in self.data_db:
			return
		if block_index >= self.get_block_num_in_piece(piece_index):
			return
		if len(data) != self.get_block_size(piece_index, block_index):
			return
		self.data_db[db_index] = data

		if piece_index in self.comp_db:
			self.comp_db[piece_index] += 1
		else:
			self.comp_db[piece_index] = 1

		self.downloaded_size += len(data)

		# validate piece_data, if failed then drop it
		num = self.get_block_num_in_piece(piece_index)
		if num == self.comp_db[piece_index] and not self.validate_piece(piece_index):
			for i in xrange(num):
				db_index = str(piece_index) + "_" + str(i)
				dropped = self.data_db.pop(db_index)
				self.downloaded_size -= len(dropped)

			db.comp_db[piece_index] = 0


	def gen_priority_list(self):
		ret = []
		for i in range(self.piece_num):
			if self.is_piece_downloading(i):
				for j in range(self.get_block_num_in_piece(i)):
					db_index = str(i) + "_" + str(j)
					if not (db_index in self.data_db):
						ret.append((i, self.get_block_offset_from_index(j), self.get_block_size(i, j)))
		return ret
	def gen_uncompleted_blocks(self, piece_index):
		ret = []
		for j in range(self.get_block_num_in_piece(piece_index)):
			db_index = str(piece_index) + "_" + str(j)
			if not (db_index in self.data_db):
				ret.append((piece_index, self.get_block_offset_from_index(j), self.get_block_size(piece_index, j)))
		return ret

	def gen_complete_str(self):
		d = [0] * ((self.piece_num - 1) / 8 + 1)
		for i in range(self.piece_num):
			index = i / 8
			mod = i % 8
			if self.is_piece_received(i):
				d[index] += 1 << (7 - mod)
		ret = ""
		for i in xrange(len(d)):
			ret += struct.pack('B', d[i])
		return ret


	def is_piece_downloading(self, piece_index):
		if not (piece_index in self.comp_db):
			return False
		if self.comp_db[piece_index] == self.get_block_num_in_piece(piece_index):
			return False
		return True

	def is_piece_received(self, piece_index):
		if not (piece_index in self.comp_db):
			return False
		if self.comp_db[piece_index] != self.get_block_num_in_piece(piece_index):
			return False
		return True

	def is_all_piece_received(self):
		for i in range(self.piece_num):
			if not self.is_piece_received(i):
				return False
		return True

	def save_target_file(self, filename):
		contents = ""
		for i in range(self.piece_num):
			contents += self.get_piece(i)
		if md5(contents).hexdigest() != self.info["md5sum"]:
			raise Exception("Md5 check failed.")
		with open(filename, 'wb') as f:
			f.write(contents)
			print '[Storage]\tsave file successfully!'

	def get_downloaded_size(self):
		return self.downloaded_size
	def get_downloaded_rate(self):
		return float(self.downloaded_size) / self.length


if __name__ == "__main__":
	info = {}
	info["piece length"] = 524288
	info["length"] = 524288 * 2 - 1
	info["md5sum"] = "123123"
	st = Storage(info)

	print(st.set_file("E:\\project\\python\\bittorrent\\python-bittorrent\\storage_test.py"))
	print(st.is_all_piece_received())
