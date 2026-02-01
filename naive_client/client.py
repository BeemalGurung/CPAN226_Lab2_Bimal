import socket
import argparse
import os
import struct

TIMEOUT_S = 0.2  # IMPROVEMENT: Retransmit if ACK not received within timeout.
MAX_RETRIES = 50  # IMPROVEMENT: Prevent infinite loop if receiver is unreachable.
CHUNK_SIZE = 4096  # IMPROVEMENT: Fixed chunk size for each UDP packet.


def run_client(target_ip, target_port, input_file):
    # 1. Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = (target_ip, target_port)
    sock.settimeout(TIMEOUT_S)  # IMPROVEMENT: Timeout enables retransmission if ACK is lost.

    print(f"[*] Sending file '{input_file}' to {target_ip}:{target_port}")

    if not os.path.exists(input_file):
        print(f"[!] Error: File '{input_file}' not found.")
        return

    try:
        with open(input_file, "rb") as f:
            seq = 0  # IMPROVEMENT: Sequence number per packet.

            while True:
                chunk = f.read(CHUNK_SIZE)  # IMPROVEMENT: Read fixed-size chunk from file.
                if not chunk:
                    break  # IMPROVEMENT: End of file reached.

                header = struct.pack("!I", seq)  # IMPROVEMENT: Prefix packet with 4-byte sequence number.
                packet = header + chunk  # IMPROVEMENT: Packet format = [seq][data].

                retries = 0  # IMPROVEMENT: Count retransmissions for this packet.
                while True:
                    sock.sendto(packet, server_address)  # IMPROVEMENT: Send or retransmit packet.
                    try:
                        ack_bytes, _ = sock.recvfrom(1024)  # IMPROVEMENT: Wait for ACK.
                        if len(ack_bytes) < 7:
                            continue  # IMPROVEMENT: Ignore malformed ACKs.
                        if ack_bytes[:3] != b"ACK":
                            continue  # IMPROVEMENT: Ignore unexpected messages.
                        ack_seq = struct.unpack("!I", ack_bytes[3:7])[0]  # IMPROVEMENT: Extract ACK seq.
                        if ack_seq == seq:
                            break  # IMPROVEMENT: Correct ACK received.
                    except socket.timeout:
                        retries += 1  # IMPROVEMENT: Timeout → retransmit.
                        if retries >= MAX_RETRIES:
                            raise RuntimeError("Max retries reached; server not responding.")

                seq += 1  # IMPROVEMENT: Move to next sequence number.

            # Send EOF marker reliably
            eof_seq = 0xFFFFFFFF  # IMPROVEMENT: Special sequence number for EOF.
            eof_packet = struct.pack("!I", eof_seq)  # IMPROVEMENT: EOF packet is just the header.

            retries = 0  # IMPROVEMENT: Retransmit EOF marker until ACKed.
            while True:
                sock.sendto(eof_packet, server_address)  # IMPROVEMENT: Send EOF marker.
                try:
                    ack_bytes, _ = sock.recvfrom(1024)  # IMPROVEMENT: Wait for EOF ACK.
                    if len(ack_bytes) < 7 or ack_bytes[:3] != b"ACK":
                        continue  # IMPROVEMENT: Ignore malformed ACKs.
                    ack_seq = struct.unpack("!I", ack_bytes[3:7])[0]  # IMPROVEMENT: Extract ACK seq.
                    if ack_seq == eof_seq:
                        break  # IMPROVEMENT: EOF acknowledged.
                except socket.timeout:
                    retries += 1  # IMPROVEMENT: Timeout → resend EOF.
                    if retries >= MAX_RETRIES:
                        raise RuntimeError("Max retries reached sending EOF.")

        print("[*] File transmission complete.")  # IMPROVEMENT: Confirm completion after EOF ACK.

    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reliable UDP File Sender (Stop-and-Wait)")
    parser.add_argument("--target_ip", type=str, default="127.0.0.1", help="Destination IP (Relay or Server)")
    parser.add_argument("--target_port", type=int, default=12000, help="Destination Port")
    parser.add_argument("--file", type=str, required=True, help="Path to file to send")
    args = parser.parse_args()

    run_client(args.target_ip, args.target_port, args.file)