#!/usr/bin/env python3

import sys

from Crypto.PublicKey import RSA

# A quick and dirty script to generate an RSA key

if len(sys.argv) != 4:
    sys.exit("Usage: {} <number of bits> <public key path> <private key path>".format(sys.argv[0]))
    
key = RSA.generate(int(sys.argv[1]))

with open(sys.argv[2], "wb") as f_obj:
    f_obj.write(key.publickey().export_key())

with open(sys.argv[3], "wb") as f_obj:
    f_obj.write(key.export_key())
