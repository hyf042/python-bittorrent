# connection.py
# The Connection

import socket
from torrent import *
from bencode import decode, encode
from consts import consts
from bitarray import BitArray

class Connection():
	def __init__(self, peer_id, protocol, torrent):
		self.running = False

		self.is_choked = True
		self.is_interested = False
		self.is_chocked_you = True
		self.is_interested_you = False

		self.peer_id = peer_id
		self.torrent = torrent
		self.protocol = protocol
		self.pieces = BitArray(self.torrent.piece_num)

	def lost(self):
		print self.peer_id, 'lost'
		self.torrent.lostConnection(self)

	##############################
	# Event Interface
	##############################
	def choke(self):
		if not self.is_chocked_you:
			self.is_chocked_you = True
			self.protocol.sendChoke()
	def unchoke(self):
		if self.is_chocked_you:
			self.is_chocked_you = False
			self.protocol.sendUnchoke()
	def interested(self):
		if not self.is_interested_you:
			self.is_interested_you = True
			self.protocol.sendInterested()
	def uninterested(self):
		if self.is_interested_you:
			self.is_interested_you = False
			self.protocol.sendUninterested()
	def have(self, piece_index):
		self.protocol.sendHave(piece_index)
		self.checkInterested()
	def bitfield(self, pieces):
		print 'send bitfield:', len(pieces)
		self.protocol.sendBitfield(pieces)
	def request(self, block_info):
		if self.is_choked:
			return
		self.protocol.sendRequest(block_info[0], block_info[1], block_info[2])
	def piece(self, block_info, block_data):
		if self.is_chocked_you:
			return
		self.protocol.sendPiece(block_info[0], block_info[1], block_data)
	def cancel(self, block_info):
		self.protocol.sendCancel(block_info[0], block_info[1], block_info[2])

	##############################
	# Event Handler
	##############################
	def chokeBy(self):
		self.is_choked = True
	def unchokeBy(self):
		self.is_choked = False
		self.torrent.onUnchoked(self)
	def interestedBy(self):
		self.is_interested = True
	def uninterestedBy(self):
		self.is_interested = False
	def haveBy(self, piece_index):
		self.pieces.set(piece_index, 1)
		self.checkInterested()
	def  bitfieldBy(self, bitfield):
		self.pieces.set_complete_str(bitfield)
		self.checkInterested()
	def requestBy(self, piece_index, block_offset, block_length):
		block_info = (piece_index, block_offset, block_length)
		if not self.is_interested or self.is_chocked_you:
			print self.peer_id, 'can not request me!'
		elif not self.torrent.checkBlockInfo(block_info):
			print self.peer_id, 'invalid block info!'
		else:
			self.torrent.onRequest(self, (piece_index, block_offset, block_length))
	def pieceBy(self, piece_index, block_offset, block_data):
		block_info = (piece_index, block_offset, len(block_data))
		if not self.torrent.checkBlockInfo(block_info):
			print self.peer_id, 'invalid block info!'
		else:
			self.torrent.onPiece(self, (piece_index, block_offset, len(block_data)), block_data)
	def cancelBy(self, piece_index, block_offset, block_length):
		block_info = (piece_index, block_offset, block_length)
		if not self.torrent.checkBlockInfo(block_info):
			print self.peer_id, 'invalid block info!'
		else:
			self.torrent.onCancel(self, (piece_index, block_offset, block_length))

	##############################
	# Utils
	##############################
	def hasPiece(self, piece_index):
		return self.pieces.get(piece_index) > 0
	def checkInterested(self):
		interested = False
		for piece_index in xrange(0, self.pieces.length):
			if not self.torrent.hasPiece(piece_index):
				interested = True
				break
		if interested != self.is_interested_you:
			if interested:
				self.interested()
			else:
				self.uninterested()
	def getDownloadRate(self):
		return self.protocol.getDownloadRate()
	def resetMeasurement(self):
		self.protocol.resetMeasurement()



