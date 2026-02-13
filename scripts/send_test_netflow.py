"""
NetFlow v5 Test Packet Generator
Sends synthetic NetFlow v5 packets to the telemetry agent to verify it's working.
"""
import socket
import struct
import time
import random

def build_netflow_v5_packet(num_flows=5):
    """Build a valid NetFlow v5 packet with the specified number of flow records."""
    # NetFlow v5 Header (24 bytes)
    version = 5
    count = num_flows
    sys_uptime = int(time.monotonic() * 1000) & 0xFFFFFFFF
    unix_secs = int(time.time())
    unix_nsecs = int((time.time() % 1) * 1e9)
    flow_sequence = random.randint(0, 0xFFFFFFFF)
    engine_type = 1
    engine_id = 0
    sampling_interval = 0

    header = struct.pack(
        '!HHIIIIBBH',
        version,        # Version (5)
        count,          # Number of flows
        sys_uptime,     # System uptime in ms
        unix_secs,      # Current seconds since epoch
        unix_nsecs,     # Residual nanoseconds
        flow_sequence,  # Sequence counter
        engine_type,    # Type of flow-switching engine
        engine_id,      # Slot number of engine
        sampling_interval  # Sampling mode and interval
    )

    # Generate flow records (48 bytes each)
    records = b''
    for i in range(num_flows):
        src_ip = socket.inet_aton(f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}")
        dst_ip = socket.inet_aton(f"172.16.{random.randint(0,255)}.{random.randint(1,254)}")
        next_hop = socket.inet_aton("10.0.0.1")

        record = struct.pack(
            '!4s4s4sHHIIIIHHxBBBHHBBxx4s',
            src_ip,                               # Source IP
            dst_ip,                               # Destination IP
            next_hop,                             # Next hop IP
            random.randint(1, 48),                # Input interface index
            random.randint(1, 48),                # Output interface index
            random.randint(100, 100000),           # Packets in flow
            random.randint(1000, 10000000),        # Bytes in flow
            sys_uptime - random.randint(1000, 60000),  # Flow start time
            sys_uptime,                           # Flow end time
            random.choice([80, 443, 8080, 22, 53, 3389]),  # Source port
            random.choice([1024, 2048, 4096, 8192, 16384]),  # Dest port
            6,                                    # TCP flags
            random.choice([6, 17, 1]),            # Protocol (TCP/UDP/ICMP)
            0,                                    # Type of service
            random.randint(64000, 65535),          # Source AS
            random.randint(64000, 65535),          # Dest AS
            24,                                   # Source prefix mask
            24,                                   # Dest prefix mask
            b'\x00\x00\x00\x00'                   # Padding
        )
        records += record

    return header + records


def main():
    target_host = "127.0.0.1"
    target_port = 2055
    num_packets = 20
    flows_per_packet = 10

    print(f"NetFlow v5 Test Generator")
    print(f"========================")
    print(f"Target: {target_host}:{target_port}")
    print(f"Sending {num_packets} packets with {flows_per_packet} flows each")
    print(f"Total flows: {num_packets * flows_per_packet}")
    print()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    total_sent = 0
    for i in range(num_packets):
        packet = build_netflow_v5_packet(flows_per_packet)
        sock.sendto(packet, (target_host, target_port))
        total_sent += flows_per_packet
        print(f"  Packet {i+1}/{num_packets}: sent {flows_per_packet} flows ({len(packet)} bytes)")
        time.sleep(0.1)  # Small delay between packets

    sock.close()

    print(f"\nDone! Sent {total_sent} total flows in {num_packets} packets.")
    print(f"Check the telemetry agent logs for processing statistics.")
    print(f"\nWait ~30 seconds for the next stats report, or check:")
    print(f"  docker compose exec timescaledb psql -U netweaver -d netweaver -c 'SELECT COUNT(*) FROM flow_records;'")


if __name__ == "__main__":
    main()
