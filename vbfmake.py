#!/usr/bin/env python3

"""
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.
This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import argparse
from pathlib import Path
from struct import pack

from crccheck.crc import Crc16CcittFalse

from ford.vbf import Vbf

header = """vbf_version = 2.3;

header {{
    sw_part_number = "{}";
    sw_part_type = {};
    data_format_identifier = 0x00;
    network = {};
    ecu_address = {};
    frame_format = {};

    {}

    file_checksum = 0xdeadbeef;
}}"""

def die(str):
	print(str)
	sys.exit(-1)

def ck_list(algos):
	print("\t[!] Can't find suitable checksum algorithm. Available --sw options: ", end='')
	for a in algos:
		print("{} ".format(a),end='')
	print()

def ck_g1f7_14c367(blocks):
	c = Crc16CcittFalse.calc(blocks[0][2][0x100:])
	c1 = c & 0xff
	c2 = c >> 8
	
	print("\t[+] Checksum 0x{:02x}{:02x}. ".format(c1, c2), end='')
	if c1 == blocks[0][2][0xa4] and c2 == blocks[0][2][0xa5]:
		print("Correct!")
	else:
		blocks[0][2][0xa4] = c1
		blocks[0][2][0xa5] = c2
		print("Fixed!")

def ck_g1f7_14c366(blocks):
	last = False
	for b in blocks:
		if not last or b[0] > last[0]:
			last = b

	hend = last[2][-6:-2]
	if hend != b'\x20\x20\x20\x20':
		print("[!] Can't find checksum section in the last segment ...")
		return False

	pos = len(last[2])-16
	while pos and last[2][pos:pos+4] != b'\x10\x10\x10\x10':
		pos = pos - 1
		hpos = pos

	if not pos:
		print("[!] Can't find checksum section in the last segment ...")
		return False

	n = (last[2][pos+5] << 8) + last[2][pos+4]

	print("\t[+] Found {} entries checksum section in segment 0x{:08x} offset 0x{:08x}".format(n, last[0], pos))

	pos = pos + 6
	for a in range(n):
		addr = (last[2][pos+3] << 24 ) + (last[2][pos+2] << 16) + (last[2][pos+1] << 8) + last[2][pos]
		pos = pos + 4
		l = (last[2][pos+3] << 24 ) + (last[2][pos+2] << 16) + (last[2][pos+1] << 8) + last[2][pos]
		pos = pos + 4
		c = (last[2][pos+1] << 8) + last[2][pos]

		print("\t\t[+] 0x{:08x}: ".format(addr), end="")

		found = False
		for b in blocks:
			if b[0] <= addr and addr <= b[0] + b[1]:
				found = b

		if not found:
			print("Not found!\r\t\t[-")
		else:
			offset = addr - found[0]
			print("Found at 0x{:08x}+{:x}, ".format(found[0], offset), end="")
			val = 0
			for i in range(l):
				val = (val + found[2][offset+i]) & 0xffff 
			print("checksum 0x{:04x}. ".format(val), end="")
			if val == c:
				print("Correct!")
			else:
				last[2][pos+1] = val >> 8
				last[2][pos] = val & 0xff
				print("Fixed!")

		pos = pos + 2

	val = 0
	for i in range(n*10+10):
		val = (val + last[2][hpos+i]) & 0xffff
	print("\t[+] Header checksum: 0x{:02x}. ".format(val), end="")

	hc = (last[2][hpos+i+2] << 8) + last[2][hpos+i+1]
	if val == hc:
		print("Correct!")
	else:
		last[2][hpos+i+2] = val >> 8
		last[2][hpos+i+1] = val & 0xff
		print("Fixed!")


def ck_f1ft_14c104(blocks):
	tab = [ 0x00, 0x00, 0xc0, 0xc1, 0xc1, 0x81, 0x01, 0x40, 0xc3, 0x01, 0x03, 0xc0, 0x02, 0x80, 0xc2, 0x41, \
			0xc6, 0x01, 0x06, 0xc0, 0x07, 0x80, 0xc7, 0x41, 0x05, 0x00, 0xc5, 0xc1, 0xc4, 0x81, 0x04, 0x40, \
			0xcc, 0x01, 0x0c, 0xc0, 0x0d, 0x80, 0xcd, 0x41, 0x0f, 0x00, 0xcf, 0xc1, 0xce, 0x81, 0x0e, 0x40, \
			0x0a, 0x00, 0xca, 0xc1, 0xcb, 0x81, 0x0b, 0x40, 0xc9, 0x01, 0x09, 0xc0, 0x08, 0x80, 0xc8, 0x41, \
			0xd8, 0x01, 0x18, 0xc0, 0x19, 0x80, 0xd9, 0x41, 0x1b, 0x00, 0xdb, 0xc1, 0xda, 0x81, 0x1a, 0x40, \
			0x1e, 0x00, 0xde, 0xc1, 0xdf, 0x81, 0x1f, 0x40, 0xdd, 0x01, 0x1d, 0xc0, 0x1c, 0x80, 0xdc, 0x41, \
			0x14, 0x00, 0xd4, 0xc1, 0xd5, 0x81, 0x15, 0x40, 0xd7, 0x01, 0x17, 0xc0, 0x16, 0x80, 0xd6, 0x41, \
			0xd2, 0x01, 0x12, 0xc0, 0x13, 0x80, 0xd3, 0x41, 0x11, 0x00, 0xd1, 0xc1, 0xd0, 0x81, 0x10, 0x40, \
			0xf0, 0x01, 0x30, 0xc0, 0x31, 0x80, 0xf1, 0x41, 0x33, 0x00, 0xf3, 0xc1, 0xf2, 0x81, 0x32, 0x40, \
			0x36, 0x00, 0xf6, 0xc1, 0xf7, 0x81, 0x37, 0x40, 0xf5, 0x01, 0x35, 0xc0, 0x34, 0x80, 0xf4, 0x41, \
			0x3c, 0x00, 0xfc, 0xc1, 0xfd, 0x81, 0x3d, 0x40, 0xff, 0x01, 0x3f, 0xc0, 0x3e, 0x80, 0xfe, 0x41, \
			0xfa, 0x01, 0x3a, 0xc0, 0x3b, 0x80, 0xfb, 0x41, 0x39, 0x00, 0xf9, 0xc1, 0xf8, 0x81, 0x38, 0x40, \
			0x28, 0x00, 0xe8, 0xc1, 0xe9, 0x81, 0x29, 0x40, 0xeb, 0x01, 0x2b, 0xc0, 0x2a, 0x80, 0xea, 0x41, \
			0xee, 0x01, 0x2e, 0xc0, 0x2f, 0x80, 0xef, 0x41, 0x2d, 0x00, 0xed, 0xc1, 0xec, 0x81, 0x2c, 0x40, \
			0xe4, 0x01, 0x24, 0xc0, 0x25, 0x80, 0xe5, 0x41, 0x27, 0x00, 0xe7, 0xc1, 0xe6, 0x81, 0x26, 0x40, \
			0x22, 0x00, 0xe2, 0xc1, 0xe3, 0x81, 0x23, 0x40, 0xe1, 0x01, 0x21, 0xc0, 0x20, 0x80, 0xe0, 0x41, \
			0xa0, 0x01, 0x60, 0xc0, 0x61, 0x80, 0xa1, 0x41, 0x63, 0x00, 0xa3, 0xc1, 0xa2, 0x81, 0x62, 0x40, \
			0x66, 0x00, 0xa6, 0xc1, 0xa7, 0x81, 0x67, 0x40, 0xa5, 0x01, 0x65, 0xc0, 0x64, 0x80, 0xa4, 0x41, \
			0x6c, 0x00, 0xac, 0xc1, 0xad, 0x81, 0x6d, 0x40, 0xaf, 0x01, 0x6f, 0xc0, 0x6e, 0x80, 0xae, 0x41, \
			0xaa, 0x01, 0x6a, 0xc0, 0x6b, 0x80, 0xab, 0x41, 0x69, 0x00, 0xa9, 0xc1, 0xa8, 0x81, 0x68, 0x40, \
			0x78, 0x00, 0xb8, 0xc1, 0xb9, 0x81, 0x79, 0x40, 0xbb, 0x01, 0x7b, 0xc0, 0x7a, 0x80, 0xba, 0x41, \
			0xbe, 0x01, 0x7e, 0xc0, 0x7f, 0x80, 0xbf, 0x41, 0x7d, 0x00, 0xbd, 0xc1, 0xbc, 0x81, 0x7c, 0x40, \
			0xb4, 0x01, 0x74, 0xc0, 0x75, 0x80, 0xb5, 0x41, 0x77, 0x00, 0xb7, 0xc1, 0xb6, 0x81, 0x76, 0x40, \
			0x72, 0x00, 0xb2, 0xc1, 0xb3, 0x81, 0x73, 0x40, 0xb1, 0x01, 0x71, 0xc0, 0x70, 0x80, 0xb0, 0x41, \
			0x50, 0x00, 0x90, 0xc1, 0x91, 0x81, 0x51, 0x40, 0x93, 0x01, 0x53, 0xc0, 0x52, 0x80, 0x92, 0x41, \
			0x96, 0x01, 0x56, 0xc0, 0x57, 0x80, 0x97, 0x41, 0x55, 0x00, 0x95, 0xc1, 0x94, 0x81, 0x54, 0x40, \
			0x9c, 0x01, 0x5c, 0xc0, 0x5d, 0x80, 0x9d, 0x41, 0x5f, 0x00, 0x9f, 0xc1, 0x9e, 0x81, 0x5e, 0x40, \
			0x5a, 0x00, 0x9a, 0xc1, 0x9b, 0x81, 0x5b, 0x40, 0x99, 0x01, 0x59, 0xc0, 0x58, 0x80, 0x98, 0x41, \
			0x88, 0x01, 0x48, 0xc0, 0x49, 0x80, 0x89, 0x41, 0x4b, 0x00, 0x8b, 0xc1, 0x8a, 0x81, 0x4a, 0x40, \
			0x4e, 0x00, 0x8e, 0xc1, 0x8f, 0x81, 0x4f, 0x40, 0x8d, 0x01, 0x4d, 0xc0, 0x4c, 0x80, 0x8c, 0x41, \
			0x44, 0x00, 0x84, 0xc1, 0x85, 0x81, 0x45, 0x40, 0x87, 0x01, 0x47, 0xc0, 0x46, 0x80, 0x86, 0x41, \
			0x82, 0x01, 0x42, 0xc0, 0x43, 0x80, 0x83, 0x41, 0x41, 0x00, 0x81, 0xc1, 0x80, 0x81, 0x40, 0x40 ]

	cksum = 0x701

	n = (blocks[0][2][0x0e] << 8) + blocks[0][2][0x0f]
	if not n:
		print("\t[!] Can't find checksum section")
		return False

	for i in range(n):
		start = (blocks[0][2][0x10 + i * 0x08] << 24) + (blocks[0][2][0x11 + i * 0x08] << 16) + (blocks[0][2][0x12 + i * 0x08] << 8) + blocks[0][2][0x13 + i * 0x08]
		end = (blocks[0][2][0x14+ i * 0x08] << 24) + (blocks[0][2][0x15 + i * 0x08] << 16) + (blocks[0][2][0x16 + i * 0x08] << 8) + blocks[0][2][0x17 + i * 0x08]

		found = None
		for b in blocks:
			if start >= b[0] and end <= b[0]+b[1]:
				found = b

		if not found:
			print("\t[!] Can't find matching block for checksum segment 0x{:08x} - 0x{:08x}".format(start, end))
			return False

		print("\t[+] Calculating checksum for 0x{:08x} - 0x{:08x} in block 0x{:08x}... ".format(start, end, found[0]), end="")


		for x in found[2][start-found[0]:end-found[0]+1]:
			x = ((cksum ^ x) << 1) & 0x1ff
			t = (tab[x] << 8) + tab[x+1]
			cksum = (cksum >> 8) ^ t

		print("OK")

	print("[+] Checksum: 0x{:04x}. ".format(cksum), end="")
	ck1 = cksum >> 8
	ck2 = cksum & 0xff

	if blocks[0][2][0x0c] == ck1 and blocks[0][2][0x0d] == ck2:
		print("Correct!")
	else:
		blocks[0][2][0x0c] = ck1
		blocks[0][2][0x0d] = ck2
		print("Fixed!")


def fix_checksum(sw, blocks):
	algos = {
		"G1F7-14C366": ck_g1f7_14c366,
		"HP57-14C366": ck_g1f7_14c366,
		"G1F7-14C367": ck_g1f7_14c367,
		"F1FT-14C104": ck_f1ft_14c104
	}

	if len(sw.split('-')) > 2:
		sw = '-'.join(sw.split('-')[0:2])

	print('\n[*] Calculating checksum for {} ...'.format(sw))
	algos.get(sw, lambda a: ck_list(algos))(blocks)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Create VBF file containing 1+ blocks represented by addr:path pairs")
	parser.add_argument("--out", help="Outpu VBF file", required=True)
	parser.add_argument("--ecu", help="ECU address (like 0x760)", required=True)
	parser.add_argument("--can", help="CAN_HS or CAN_MS, HS by default", default="CAN_HS")
	parser.add_argument("--type", help="[SBL,EXE,SIG,...]", default="EXE")
	parser.add_argument("--sw", help="Software part number", default="")
	parser.add_argument("--call", help="Address to call, SBL block iteself by default", default=None)
	parser.add_argument("--frame-format", help="CAN frame format. Can be CAN_STANDARD (default) or CAN_EXTENDED", default="CAN_STANDARD")
	parser.add_argument("--erase-blocks", help="Comma separated list of blocks to erase before writing", default=False)
	parser.add_argument("--erase-memory", type=str, help='Comma separated list of memory ranges to erase described as addr:size')
	parser.add_argument("blocks", metavar='addr:path', type=str, nargs='+', help='list of blocks described as addr:path')
	parser.add_argument("--fix-checksum", help="Try to calculate known checksums, algorithm selection based on --sw", default=False, action='store_true')

	args = parser.parse_args()

	print("[*] Generating {} VBF file for {}".format(args.type, args.ecu))

	blocks = list()
	for p in args.blocks:
		addr,path = p.split(':')
		path = Path(path)

		addr = int(addr, 16)
		if not path.is_file():
			die("[!] Can't open {}".format(path))

		size = path.stat().st_size

		f = open(path, 'rb')
		data = f.read()
		blocks.append([addr, size, bytearray(data)])

		print("\t[+] Adding 0x{:x} bytes block from {} at 0x{:08x}".format(path.stat().st_size, path, addr))

	body = str()

	calladdr = False

	if args.type == "SBL":
		calladdr = "0x{:08x}".format(blocks[0][0])

	if args.call:
		if args.type != "SBL":
			print("[-] Does it really make sens to use call for non-SBL?!")
			calladdr = args.call
	
	if calladdr:
		body += "call = {};\n".format(args.call)
	
	e = str()

	if args.erase_blocks:
		for n in args.erase_blocks.split(','):
			b = blocks[int(n)-1]
			e += "{{ 0x{:08x}, 0x{:08x} }},".format(b[0], b[1])

	if args.erase_memory:
		for n in args.erase_memory.split(','):
			a = n.split(':')[0]
			b = n.split(':')[1]
			e += "{{ {}, {} }},".format(a, b)			

	if e:
		body += "erase = {{ {} }};".format(e[:-1])

	header = header.format(args.sw, args.type, args.can, args.ecu, args.frame_format, body)

	if args.fix_checksum:
		fix_checksum(args.sw, blocks)

	print("\n[ ] Writing {} ...".format(args.out), end='')
	with open(args.out, 'wb') as f:
		f.write(header.encode("ASCII"))
		for b in blocks:
			crc = Crc16CcittFalse.calc(b[2])
			print("\n\t[ ] 0x{:x} bytes block (CRC 0x{:04x}) at 0x{:08x}... ".format(b[1], crc, b[0]), end='')
			f.write(pack('>II', b[0], b[1]))
			f.write(b[2])
			f.write(pack('>H', crc))
			print("OK\r\t[+", end='')
		print('\n[+] Done')
