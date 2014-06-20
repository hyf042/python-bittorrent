import struct

class BitArray:

	def __init__(self, length):
		self.reset(length)

	def reset(self, length):
		self.length = length
		self.count = (length - 1) / 32 + 1
		self.data = [0] * self.count

	def get(self, index):
		if index >= self.length:
			return
		data_index = index >> 5
		data_mod = index & 31
		return (self.data[data_index] >> data_mod) & 1

	def set(self, index, value):
		if index >= self.length:
			return
		data_index = index >> 5
		data_mod = index & 31
		if (value&1) == 1:
			if ((self.data[data_index] >> data_mod) & 1) == 0:
				self.data[data_index] += (1 << data_mod)
		else:
			if ((self.data[data_index] >> data_mod) & 1) == 1:
				self.data[data_index] -= (1 << data_mod)

	def gen_complete_str(self):
		d = [0] * self.count
		for i in range(self.length):
			index = i / 8
			mod = i % 8
			if self.get(i) == 1:
				d[index] += 1 << (7 - mod)
		ret = ""
		for i in xrange(len(d)):
			ret += struct.pack('B', d[i])
		return ret

	def to_str(self):
		s = ""
		for i in xrange(self.length):
			s += str(self.get(i))
		return s

if __name__ == '__main__':
	b = BitArray(10)
	print b.to_str()
	b.set(1, 1)
	print b.to_str()
	print b.get(1)
	b.set(2, 1)
	print b.to_str()
	b.set(7, 1)
	print b.to_str()
	print b.gen_complete_str()