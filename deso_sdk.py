def create_key_pair_from_seed_or_seed_hex(
	seed: str,
	passphrase: str,
	index: int,
	is_testnet: bool
) -> tuple:
	"""
	Creates a key pair from either a seed phrase or seed hex.

	Args:
		seed (str): Either a BIP39 mnemonic seed phrase or a hex string
		passphrase (str): Optional passphrase for BIP39 seed
		index (int): Account index for derivation path
		is_testnet (bool): Whether to use testnet or mainnet parameters

	Returns:
		Tuple[DeSoKeyPair, Optional[str]]: Returns the key pair and any error message
	"""
	if not seed:
		return None, "Seed must be provided"

	# First try to decode as hex to determine if it's a seed hex
	try:
		seed_bytes = binascii.unhexlify(seed.lower())
		# If we get here, it's a valid hex string
		if passphrase or index != 0:
			return None, "Seed hex provided, but passphrase or index params were also provided"

		# Convert the seed hex directly to keys
		privkey = PrivateKey(seed_bytes)
		pubkey = privkey.public_key
		return DeSoKeyPair(pubkey.format(), privkey.secret), None

	except binascii.Error:
		# Not a valid hex string, treat as mnemonic
		try:
			# Validate and convert mnemonic to seed
			mnemo = Mnemonic("english")
			if not mnemo.check(seed):
				return None, "Invalid mnemonic seed phrase"

			seed_bytes = mnemo.to_seed(seed, passphrase)

			# Initialize BIP32 with appropriate network
			network = "test" if is_testnet else "main"
			bip32 = BIP32.from_seed(seed_bytes, network=network)

			# Derive the key path: m/44'/0'/index'/0/0
			# Note: in BIP32, hardened keys are represented with index + 0x80000000
			path = f"m/44'/0'/{index}'/0/0"
			derived_key = bip32.get_privkey_from_path(path)

			# Convert to coincurve keys for consistent interface
			privkey = PrivateKey(derived_key)
			pubkey = privkey.public_key

			return DeSoKeyPair(pubkey.format(), privkey.secret), None

		except Exception as e:
			return None, f"Error converting seed to key pair: {str(e)}"
class DeSoDexClient:
	# A Python client for interacting with the DeSo DEX endpoints on a DeSo node.

	def __init__(self, is_testnet: bool=False, seed_phrase_or_hex=None, passphrase=None, index=0, node_url=None):
		self.is_testnet = is_testnet

		desoKeyPair, err = create_key_pair_from_seed_or_seed_hex(
			seed_phrase_or_hex, passphrase, index, is_testnet,
		)
		if desoKeyPair is None:
			raise ValueError(err)
		self.deso_keypair = desoKeyPair

		if node_url is None:
			if is_testnet:
				node_url = "https://test.deso.org"
			else:
				node_url = "https://node.deso.org"
		self.node_url = node_url.rstrip("/")

	# Add all other methods from the SDK fork as needed for full functionality
import hashlib
import json

import requests
from typing import Optional, Dict, Any, List, Union
from pprint import pprint
import sys

from typing import Tuple, Optional
import binascii
from bip32 import BIP32, base58
from mnemonic import Mnemonic
from coincurve import PrivateKey
	seed: str,

