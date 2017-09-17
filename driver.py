#!/usr/bin/python
from __future__ import absolute_import, print_function, division
import argparse
import os
import socket
import sys

# <lenH><lenL> <what_command> <delay> <start_index> <length> <r><g><b>...
def _add_length(cmd):
    """Add two big-endian bytes of length to the front of this command"""
    length = len(cmd)
    assert 0 < length <= 2**16
    lenH = length // 256
    lenL = length % 256
    return bytes([lenH, lenL]) + cmd

def build_command_write(start, pixels, delay):
    """Build a write command.

    Format:
      <lenH><lenL><(w)rite><delay><start_index><num_pixels><r1><g1><b1><r2><g2><b2>...

    Args:
      start (int 8-bit): first pixel to write
      pixels (list of 3-tuples, RGB): pixels to write
      delay (int 8-bit): delay after command in ms
    Returns:
      command as bytestring
    """
    for pix in pixels:
        assert len(pix) == 3
    pix_colors = [x for y in pixels for x in y]  # flatten
    assert 0 <= delay < 256
    assert 0 <= len(pixels) < 256
    assert 0 <= start < 256
    for byt in pix_colors:
        assert 0 <= byt < 256
    cmd = bytes([ord('w'), delay, start, len(pixels)] + pix_colors)
    return _add_length(cmd)

def build_packet(commands):
    """Build a packet made of 0 to N command bytestrings"""
    return b''.join(commands) + b'\x00\x00'

def send_one_write(args):
    # Send a single write to the specified host and disconnect
    s = socket.socket()
    s.connect((args.host, args.port))
    pixels = [[]]
    for x in args.rgb:
        if len(pixels[-1]) == 3:
            pixels.append([])
        pixels[-1].append(x)
    pkt = build_packet([build_command_write(args.start, pixels, args.delay)])
    print("Sending packet: %r" % pkt, file=sys.stderr)
    s.send(pkt)
    s.close()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--host", help="IP address to connect to")
    parser.add_argument("-p", "--port", type=int, default=1000, help="Port to connect to (default: 10000)")
    subparsers = parser.add_subparsers(title='subcommands')

    write_parser = subparsers.add_parser('write')
    write_parser.set_defaults(func=send_one_write)
    write_parser.add_argument("--delay", type=int, default=0, help="Delay after write (default: 0)")
    write_parser.add_argument("--start", type=int, default=0, help="First LED to change (default: 0)")
    write_parser.add_argument("rgb", type=int, nargs='*', help="R/G/B of pixel (specify R1 G1 B1 R2 G2 B2 ...)")

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
