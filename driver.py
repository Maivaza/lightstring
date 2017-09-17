#!/usr/bin/python3
from __future__ import absolute_import, print_function, division
import argparse
import collections
import os
import socket
import sys
import re
import time

MAX_PKT_LEN = 32768

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
    pkt = b''.join(commands) + b'\x00\x00'
    if len(pkt) > MAX_PKT_LEN:
        raise ValueError("Packet too large")
    return pkt

def color_to_rgb(color):
    m = re.match(r'(?i)([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})', color)
    if m:
        return tuple(int(x, 16) for x in m.groups())

    m = re.match(r'([0-9]{1,3}),([0-9]{1,3}),([0-9]{1,3})', color)
    if m:
        return tuple(int(x) for x in m.groups())

    try:
        import webcolors
        return webcolors.name_to_rgb(color)
    except ImportError:
        raise ValueError("Unrecognized color: %r - (note: webcolors not installed)" % color)
    except Exception:
        raise ValueError("Unrecognized color: %r" % color)

def scale_pixels(pixels, sf):
    return [(int(r * sf), int(g * sf), int(b * sf)) for (r, g, b) in pixels]

def lerp(a, b, t, steps):
    return a + t * (b - a) / steps

def flatten(pixels):
    return [x for y in pixels for x in y]

def structure(flat_pix):
    pixels = [[]]
    for x in flat_pix:
        if len(pixels[-1]) == 3:
            pixels[-1] = tuple(pixels[-1])
            pixels.append([])
        pixels[-1].append(x)
    assert len(pixels[-1]) == 3
    return pixels

def lerp_pixels(pixelsA, pixelsB, t, steps):
    return structure([int(lerp(a, b, t, steps)) for (a, b) in zip(flatten(pixelsA), flatten(pixelsB))])

def fade(pixelsA, pixelsB, ms, steps):
    commands = []
    for step in range(steps):
        pixels = lerp_pixels(pixelsA, pixelsB, step, steps)
        commands.append(build_command_write(0, pixels, ms // steps))
    return commands

def write_cmd_as_display_string(cmd):
    pixels = structure(cmd[6:])
    return '(%s) ' % (cmd[3]) + ''.join(['O' if pix != (0,0,0) else '_' for pix in pixels])

def send_one_packet(host, port, commands):
    pkt = build_packet(commands)

    s = socket.socket()
    s.connect((host, port))
    #print("Sending packet: %r" % pkt, file=sys.stderr)
    s.send(pkt)
    s.close()

def send_one_write(args):
    # Send a single write to the specified host and disconnect
    pixels = [color_to_rgb(col) for col in args.color] * args.repeat
    pixels = scale_pixels(pixels, args.brightness / 100.0)
    cmds = [build_command_write(args.start, pixels, args.delay)]
    send_one_packet(args.host, args.port, cmds)

def send_commands(host, port, command_iter):
    s = socket.socket()
    s.connect((host, port))

    cmds = []
    for cmd in command_iter:
        try:
            build_packet(cmds + [cmd])
        except ValueError:
            print("Packet contains commands:")
            for cmd in cmds:
                print(write_cmd_as_display_string(cmd))
            print()

            pkt = build_packet(cmds)
            cmds = []
            #print("Sending packet: %r" % pkt, file=sys.stderr)
            s.send(pkt)

        cmds.append(cmd)

    if cmds:
        print("Packet contains commands:")
        for cmd in cmds:
            print(write_cmd_as_display_string(cmd))
        print()
        pkt = build_packet(cmds)
        cmds = []
        #print("Sending packet: %r" % pkt, file=sys.stderr)
        s.send(pkt)

    s.close()

def parse_colors(cpixels):
    return [color_to_rgb(c) for c in cpixels]

def shift(pixels, direction, ms, steps):
    commands = []
    pixels = collections.deque(pixels)
    delay = ms // steps
    delays = [255] * (delay // 256) + [delay % 256]
    for step in range(steps):
        for delay in delays:
            commands.append(build_command_write(0, list(pixels), delay))
        if direction > 0:
            pixels.append(pixels.popleft())
        elif direction < 0:
            pixels.appendleft(pixels.pop())
    return commands

def white_cycle(num_pix, ms):
    pixels = collections.deque([(8,8,8)] + [(0,0,0)] * (num_pix - 1))
    delay = ms // num_pix
    delays = [255] * (delay // 256) + [delay % 256]
    direction = 1
    while True:
        for delay in delays:
            yield build_command_write(0, list(pixels), delay)
        if direction > 0:
            pixels.append(pixels.popleft())
        elif direction < 0:
            pixels.appendleft(pixels.pop())
        if pixels[0][0]:
            direction *= -1

def compute_total_delay(cmds):
    return sum(cmd[3] for cmd in cmds if cmd[2] == b'w')

def streamer_white_cycle(conn, num_pix, ms_half):
    WHITE = (8,8,8)
    BLACK = (0,0,0)
    direction = 1
    pixels = collections.deque([WHITE] + [BLACK] * num_pix)

    delay = ms_half // num_pix
    delays = [255] * (delay // 256) + [delay % 256]

    while True:
        for delay in delays:
            conn.send_buffered(build_command_write(0, list(pixels), delay))

        if direction == 1:
            pixels.appendleft(pixels.pop())
            if pixels[-1] == WHITE:
                direction = -1
        else:
            pixels.append(pixels.popleft())
            if pixels[0] == WHITE:
                direction = 1

class Streamer(object):
    def __init__(self, host, port=10000):
        self.host = host
        self.port = port
        self.socket = None
        self.cmd_buffer = []

    def connect(self):
        self.socket = socket.socket()
        self.socket.connect((self.host, self.port))

    def send_buffered(self, cmd):
        if not self.socket:
            self.connect()

        try:
            build_packet(self.cmd_buffer + [cmd])
        except ValueError:
            self.flush()

        self.cmd_buffer.append(cmd)

    def flush(self):
        if self.cmd_buffer:
            pkt = build_packet(self.cmd_buffer)
            self.socket.send(pkt)
            total_delay = compute_total_delay(self.cmd_buffer)
            time.sleep((total_delay - 10) / 1000)
            self.cmd_buffer = []

    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--host", help="IP address to connect to")
    parser.add_argument("-p", "--port", type=int, default=1000, help="Port to connect to (default: 10000)")
    subparsers = parser.add_subparsers(title='subcommands')

    write_parser = subparsers.add_parser('write')
    write_parser.set_defaults(func=send_one_write)
    write_parser.add_argument('--brightness', type=float, default=100.0,
                              help="Scale brightness to this percent (default: 100)")
    write_parser.add_argument("--delay", type=int, default=0, help="Delay after write (default: 0)")
    write_parser.add_argument("--start", type=int, default=0, help="First LED to change (default: 0)")
    write_parser.add_argument("--repeat", type=int, default=1, help="Number of times to repeat color sequence given (default: 1)")
    write_parser.add_argument("color", nargs='*', help="Color of pixel: dec r,g,b; hex rrggbb; any html color name")

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    #conn = Streamer('192.168.60.206')
    #streamer_white_cycle(conn, 10, 1000)
    #send_commands('192.168.60.207', 10000, white_cycle(10, 1000))
    main()
