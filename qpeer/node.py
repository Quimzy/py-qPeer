#!/usr/bin/python3

from qpeer.errors import *
from qpeer.utils import Utils
import socket
import struct
import os
import hashlib
from base64 import b64encode, b64decode

utils = Utils()

class Client:
	def __init__(self):
		self.peers = utils.peers
		self.temp_peers = utils.temp_peers
		self.offline_peers = utils.offline_peers		

	def setup(self,peerip,peerport):
		soc = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		soc.connect((peerip,peerport))
		
		def greet():
			msg = utils.qpeer()
			soc.send(msg)
			recvd = soc.recv(2048)
			if recvd:
				return recvd
			else:
				raise InitError
				soc.close()

		def handle_greet():
			msg_greet = utils.unpack_init(greet())
			return msg_greet[0],b64decode(msg_greet[1])

		peerid, pubkey_pem = handle_greet()
		
		if peerid.decode() == hashlib.sha1(pubkey_pem).hexdigest():
			pass
		else:
			raise IdError
			soc.close()


		AES_iv, AES_key = utils.AES_keygen()

		def send_key():
			soc.send(utils.penc_AES(AES_key,int(AES_iv),pubkey_pem))
			recvd = soc.recv(2048)
			if recvd:
				return recvd
			else:
				raise PeerinfoError
				soc.close()

		peerinfo = utils.dkenc_peerinfo(send_key(), AES_iv, AES_key)
		try:
			utils.save_lpeer(str(peerid.decode()),peerinfo,AES_iv,AES_key)
		except LpeerError:
			print('[!] Peer already exists')
			soc.close()
			pass

		def send_peerinfo():
			payload = utils.kenc_peerinfo(int(AES_iv), AES_key)
			soc.send(payload)
			recvd = soc.recv(8192)
			if recvd:
				return recvd
			else:
				raise PeersError
				soc.close()

		peers = send_peerinfo()
		try:
			utils.save_peers(peers, int(AES_iv), AES_key)
		except Exception as e:
			print(e)
			soc.close()

		def send_peers():
			payload = utils.share_peers(int(AES_iv), AES_key)
			soc.send(payload)
			recvd = soc.recv(2048)
			if recvd == utils.bye():
				soc.close()
			else:
				raise ByeError
				soc.close()

		def send_bye():
			if len(self.peers) <= 5:
				soc.send(utils.bye())
				soc.close()
			else:
				send_peers()
				soc.close()
		send_bye()

	def exchange_peers(self, peerid):
		peer = utils.decrypt_peer(peerid)
		peerinfo = peer['peerinfo']
		AES_iv, AES_key = peer['iv'], peer['key']
		ip, port = peerinfo[1:3]
		msg = utils.exchange_peers()
		soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		try:
			soc.connect((ip, port))

			#Verifying AES_key
			soc.send(msg)
			verify_payload = soc.recv(2048)
			verify_msg = utils.dkenc_verify(verify_payload,iv,key)
			soc.send(verify_msg)

			#Exchanging peers
			recvd_peers = conn.recv(8192)
			if recvd_peers:
				utils.save_peers(recvd_peers, AES_iv, AES_key)
				conn.send(utils.share_peers(AES_iv, AES_key))
			else:
				raise PeersError

			#Bye
			bye_msg = conn.recv(2048)
			if bye_msg == utils.bye():
				conn.send(utils.bye())
				soc.close()
			else:
				raise ByeError

		except socket.error:
			print("Can't connect")
			utils.remove_peer(peerid)
		except Exception as e:
			print(e)
			soc.close()




	def ping(self, peerid,peerlist=None):
		peerinfo = utils.decrypt_peer(peerid)['peerinfo']
		ip, port = peerinfo[1:3]
		msg = utils.ping()
		soc = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
		
		try:
			soc.connect((ip,port))
			soc.send(msg)
			soc.close()
		except socket.error:
			utils.remove_peer(peerid)

	def getback(self, peerid):
		peer = utils.find_peer(peerid, self.offline_peers)
		ip, port = peer['peerip'],peer['port']

		soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		try:
			soc.connect((ip, port))
			soc.close()
			utils.getback_peer(peerid)
		except socket.error:
			pass


class Server:
	def __init__(self):
		self.peers = utils.peers
		self.temp_peers = utils.temp_peers
		self.offline_peers = utils.offline_peers

	def setup(self, conn, peerid):

		def init():
			conn.send(utils.init())
			recvd = conn.recv(2048)
			if recvd:
				return recvd
			else:
				raise AesError
				conn.close()

		AES_iv, AES_key = utils.dpenc_AES(init())

		def send_peerinfo():
			conn.send(utils.kenc_peerinfo(int(AES_iv), AES_key.encode()))
			recvd = conn.recv(2048)
			if recvd:
				return recvd
			else:
				raise PeerinfoError
				conn.close()

		peerinfo = utils.dkenc_peerinfo(send_peerinfo(), int(AES_iv), AES_key.encode())
		if peerid == hashlib.sha1(b64decode(peerinfo[-1])).hexdigest():
			pass
		else:
			raise IdError
			conn.close()
		
		def send_peers():
			conn.send(utils.share_peers(int(AES_iv), AES_key.encode()))
			recvd = conn.recv(8192)
			if recvd != utils.bye() and len(recvd) > 0:
				utils.save_peers(recvd, int(AES_iv), AES_key.encode())
				conn.close()
			else:
				conn.send(utils.bye())
				conn.close()

		try:
			utils.save_lpeer(peerid, peerinfo, AES_iv, AES_key.encode())
			send_peers()
		except LpeerError:
			print("[!] Peer already exists")
			conn.close()
		except PeersError:
			print("[!] Temp Peer already exists")
			conn.close()
		except Exception as e:
			print(e)
			conn.close()
	
	def exchange_peers(self, conn, peerid):
		
		peer = utils.decrypt_peer(peerid)
		AES_iv, AES_key = peer['iv'], peer['key']
		try:
			verify_msg = os.urandom(32)
			conn.send(utils.kenc_verify(verify_msg,AES_iv,AES_key))
			verify_payload = conn.recv(2048)

			if utils.dkenc_verify(verify_payload, AES_iv, AES_key) == msg:
				conn.send(utils.share_peers(AES_iv, AES_key))
				recvd_peers = conn.recv(8192)
				if recvd_peers:
					utils.save_peers(recvd_peers, AES_iv, AES_key)
					conn.send(utils.bye())

					bye_msg = conn.recv(2048)

					if bye_msg == utils.bye():
						conn.send(utils.bye())
					else:
						raise ByeError
				else:
					raise PeersError
			else:
				raise VerifyError
		except Exception as e:
			print(e)
