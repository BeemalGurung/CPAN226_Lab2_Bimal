# This program was modified by [Bimal Gurung] / [n01658227]

import socket
import argparse
import struct

BUFFER_SIZE = 65535         # IMPROVEMENT: Max UDP packet size.
EOF_SEQ = 0xFFFFFFFF        # IMPROVEMENT: Special sequence number indicating end of file.


def run_server(listen_port, output_file):
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", listen_port))

    print(f"[*] Server listening on port {listen_port}")
    print("[*] Server will save each received file as 'received_<ip>_<port>.jpg' based on sender.")

    files = {}          # Track open files per client
    expected_seq = {}   # Track next expected sequence number per client
    buffers = {}        # Buffer out-of-order packets per client (dict: seq -> payload)

    while True:
        data, addr = sock.recvfrom(BUFFER_SIZE)  # Receive UDP packet
        client_ip, client_port = addr

        if len(data) < 4:
            continue  # Ignore malformed packets

        # Extract sequence number + payload
        seq = struct.unpack("!I", data[:4])[0]
        payload = data[4:]

        # Send ACK immediately (even if out-of-order or duplicate)
        ack = b"ACK" + struct.pack("!I", seq)
        sock.sendto(ack, addr)

        # Initialize state for first packet from this client
        if addr not in files and seq != EOF_SEQ:
            filename = f"received_{client_ip.replace('.', '_')}_{client_port}.jpg"
            files[addr] = open(filename, "wb")
            expected_seq[addr] = 0
            buffers[addr] = {}
            print(f"[*] Receiving file from {client_ip}:{client_port} → {filename}")

        # Handle EOF: close and clean up state
        if seq == EOF_SEQ:
            print(f"[*] EOF received from {client_ip}:{client_port}")
            if addr in files:
                files[addr].close()
                del files[addr]
                del expected_seq[addr]
                del buffers[addr]
            continue

        # If we haven't initialized (edge case), skip
        if addr not in files:
            continue

        # In-order write + flush buffered packets
        if seq == expected_seq[addr]:
            files[addr].write(payload)
            expected_seq[addr] += 1

            # Flush any buffered packets that are now in order
            while expected_seq[addr] in buffers[addr]:
                files[addr].write(buffers[addr][expected_seq[addr]])
                del buffers[addr][expected_seq[addr]]
                expected_seq[addr] += 1

        # Buffer out-of-order packets (only if ahead of expected)
        elif seq > expected_seq[addr]:
            buffers[addr][seq] = payload

        # Duplicate/old packets (seq < expected) are ignored safely

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reliable UDP File Receiver (ACK + ordering + buffering)")
    parser.add_argument("--port", type=int, default=12001, help="Port to listen on")
    parser.add_argument("--output", type=str, default="received.jpg", help="(Unused) Output filename")
    args = parser.parse_args()

    run_server(args.port, args.output)