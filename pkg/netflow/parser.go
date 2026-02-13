// Package netflow provides NetFlow v5, v9, and IPFIX packet parsing
// NetFlow is a network protocol developed by Cisco for collecting IP traffic information
package netflow

import (
	"encoding/binary"
	"fmt"
	"net"
	"time"
)

// NetFlow version constants
const (
	NetFlowV5   = 5
	NetFlowV9   = 9
	NetFlowIPFIX = 10 // IPFIX is also called NetFlow v10
)

// Common protocol numbers
const (
	ProtocolICMP = 1
	ProtocolTCP  = 6
	ProtocolUDP  = 17
)

// FlowRecord represents a generic flow record with all common fields
type FlowRecord struct {
	Timestamp      time.Time
	ExporterIP     net.IP
	SourceIP       net.IP
	DestinationIP  net.IP
	SourcePort     uint16
	DestPort       uint16
	Protocol       uint8
	Bytes          uint64
	Packets        uint64
	TCPFlags       uint8
	ToS            uint8  // Type of Service / DSCP
	InputInterface uint32
	OutputInterface uint32
	NextHopIP      net.IP
	SourceAS       uint32
	DestAS         uint32
	FlowDuration   uint32 // milliseconds
	SamplingRate   uint32
}

// NetFlowV5Header represents the NetFlow v5 packet header
// Total size: 24 bytes
type NetFlowV5Header struct {
	Version        uint16
	Count          uint16 // Number of flow records in packet
	SysUptime      uint32 // Milliseconds since device boot
	UnixSecs       uint32 // Seconds since 0000 UTC 1970
	UnixNsecs      uint32 // Residual nanoseconds
	FlowSequence   uint32 // Sequence counter
	EngineType     uint8  // Type of flow-switching engine
	EngineID       uint8  // Slot number of flow-switching engine
	SamplingInterval uint16 // First 2 bits: sampling mode, remaining 14 bits: sampling interval
}

// NetFlowV5Record represents a single NetFlow v5 flow record
// Total size: 48 bytes
type NetFlowV5Record struct {
	SrcAddr    [4]byte // Source IP address
	DstAddr    [4]byte // Destination IP address
	NextHop    [4]byte // IP address of next hop router
	Input      uint16  // SNMP index of input interface
	Output     uint16  // SNMP index of output interface
	DPkts      uint32  // Packets in the flow
	DOctets    uint32  // Total number of Layer 3 bytes in packets
	First      uint32  // SysUptime at start of flow
	Last       uint32  // SysUptime at last packet of flow
	SrcPort    uint16  // TCP/UDP source port number
	DstPort    uint16  // TCP/UDP destination port number
	Pad1       uint8   // Unused (zero) byte
	TCPFlags   uint8   // Cumulative OR of TCP flags
	Prot       uint8   // IP protocol type (e.g., TCP = 6, UDP = 17)
	Tos        uint8   // IP type of service (ToS)
	SrcAS      uint16  // AS number of source, either origin or peer
	DstAS      uint16  // AS number of destination, either origin or peer
	SrcMask    uint8   // Source address prefix mask bits
	DstMask    uint8   // Destination address prefix mask bits
	Pad2       uint16  // Unused (zero) bytes
}

// NetFlowV9Header represents NetFlow v9 packet header
type NetFlowV9Header struct {
	Version      uint16
	Count        uint16 // Number of FlowSet records (template and data)
	SysUptime    uint32
	UnixSecs     uint32
	PackageSequence uint32
	SourceID     uint32 // Observation domain ID
}

// NetFlowV9FlowSet represents a NetFlow v9 FlowSet
type NetFlowV9FlowSet struct {
	FlowSetID uint16 // Template ID or data FlowSet ID
	Length    uint16 // Length of this FlowSet in bytes
}

// Parser handles parsing of NetFlow packets
type Parser struct {
	// Statistics
	PacketsParsed   uint64
	RecordsParsed   uint64
	ParseErrors     uint64
}

// NewParser creates a new NetFlow parser
func NewParser() *Parser {
	return &Parser{}
}

// Parse attempts to parse a NetFlow packet and returns flow records
func (p *Parser) Parse(data []byte, exporterIP net.IP) ([]FlowRecord, error) {
	if len(data) < 2 {
		p.ParseErrors++
		return nil, fmt.Errorf("packet too short: %d bytes", len(data))
	}

	// Read version field (first 2 bytes, big-endian)
	version := binary.BigEndian.Uint16(data[0:2])

	switch version {
	case NetFlowV5:
		return p.parseV5(data, exporterIP)
	case NetFlowV9:
		return p.parseV9(data, exporterIP)
	case NetFlowIPFIX:
		return p.parseIPFIX(data, exporterIP)
	default:
		p.ParseErrors++
		return nil, fmt.Errorf("unsupported NetFlow version: %d", version)
	}
}

// parseV5 parses NetFlow v5 packets
func (p *Parser) parseV5(data []byte, exporterIP net.IP) ([]FlowRecord, error) {
	const headerSize = 24
	const recordSize = 48

	if len(data) < headerSize {
		p.ParseErrors++
		return nil, fmt.Errorf("NetFlow v5 packet too short for header: %d bytes", len(data))
	}

	// Parse header
	header := NetFlowV5Header{
		Version:          binary.BigEndian.Uint16(data[0:2]),
		Count:            binary.BigEndian.Uint16(data[2:4]),
		SysUptime:        binary.BigEndian.Uint32(data[4:8]),
		UnixSecs:         binary.BigEndian.Uint32(data[8:12]),
		UnixNsecs:        binary.BigEndian.Uint32(data[12:16]),
		FlowSequence:     binary.BigEndian.Uint32(data[16:20]),
		EngineType:       data[20],
		EngineID:         data[21],
		SamplingInterval: binary.BigEndian.Uint16(data[22:24]),
	}

	// Validate packet size
	expectedSize := headerSize + (int(header.Count) * recordSize)
	if len(data) < expectedSize {
		p.ParseErrors++
		return nil, fmt.Errorf("NetFlow v5 packet size mismatch: got %d, expected %d", len(data), expectedSize)
	}

	// Extract sampling rate (lower 14 bits of SamplingInterval)
	samplingRate := uint32(header.SamplingInterval & 0x3FFF)
	if samplingRate == 0 {
		samplingRate = 1 // No sampling
	}

	// Parse flow records
	flows := make([]FlowRecord, 0, header.Count)
	timestamp := time.Unix(int64(header.UnixSecs), int64(header.UnixNsecs))

	offset := headerSize
	for i := 0; i < int(header.Count); i++ {
		if offset+recordSize > len(data) {
			break
		}

		recordData := data[offset : offset+recordSize]
		
		// Parse record fields
		srcAddr := net.IP(recordData[0:4])
		dstAddr := net.IP(recordData[4:8])
		nextHop := net.IP(recordData[8:12])
		input := binary.BigEndian.Uint16(recordData[12:14])
		output := binary.BigEndian.Uint16(recordData[14:16])
		dPkts := binary.BigEndian.Uint32(recordData[16:20])
		dOctets := binary.BigEndian.Uint32(recordData[20:24])
		first := binary.BigEndian.Uint32(recordData[24:28])
		last := binary.BigEndian.Uint32(recordData[28:32])
		srcPort := binary.BigEndian.Uint16(recordData[32:34])
		dstPort := binary.BigEndian.Uint16(recordData[34:36])
		// byte 36 is padding
		tcpFlags := recordData[37]
		protocol := recordData[38]
		tos := recordData[39]
		srcAS := binary.BigEndian.Uint16(recordData[40:42])
		dstAS := binary.BigEndian.Uint16(recordData[42:44])
		// bytes 44-47 contain src/dst mask and padding

		// Calculate flow duration
		var flowDuration uint32
		if last >= first {
			flowDuration = last - first
		}

		// Create flow record
		flow := FlowRecord{
			Timestamp:       timestamp,
			ExporterIP:      exporterIP,
			SourceIP:        srcAddr,
			DestinationIP:   dstAddr,
			SourcePort:      srcPort,
			DestPort:        dstPort,
			Protocol:        protocol,
			Bytes:           uint64(dOctets) * uint64(samplingRate), // Account for sampling
			Packets:         uint64(dPkts) * uint64(samplingRate),
			TCPFlags:        tcpFlags,
			ToS:             tos,
			InputInterface:  uint32(input),
			OutputInterface: uint32(output),
			NextHopIP:       nextHop,
			SourceAS:        uint32(srcAS),
			DestAS:          uint32(dstAS),
			FlowDuration:    flowDuration,
			SamplingRate:    samplingRate,
		}

		flows = append(flows, flow)
		offset += recordSize
	}

	p.PacketsParsed++
	p.RecordsParsed += uint64(len(flows))

	return flows, nil
}

// parseV9 parses NetFlow v9 packets (template-based)
func (p *Parser) parseV9(data []byte, exporterIP net.IP) ([]FlowRecord, error) {
	// NetFlow v9 is template-based and requires maintaining template state
	// For simplicity, this implementation returns an error
	// A production implementation would maintain a template cache
	p.ParseErrors++
	return nil, fmt.Errorf("NetFlow v9 parsing not fully implemented yet (requires template management)")
}

// parseIPFIX parses IPFIX (NetFlow v10) packets
func (p *Parser) parseIPFIX(data []byte, exporterIP net.IP) ([]FlowRecord, error) {
	// IPFIX is similar to NetFlow v9 but with some enhancements
	// For simplicity, this implementation returns an error
	p.ParseErrors++
	return nil, fmt.Errorf("IPFIX parsing not fully implemented yet (requires template management)")
}

// GetStatistics returns parser statistics
func (p *Parser) GetStatistics() (packets, records, errors uint64) {
	return p.PacketsParsed, p.RecordsParsed, p.ParseErrors
}

// FormatProtocol returns a human-readable protocol name
func FormatProtocol(proto uint8) string {
	switch proto {
	case ProtocolICMP:
		return "ICMP"
	case ProtocolTCP:
		return "TCP"
	case ProtocolUDP:
		return "UDP"
	default:
		return fmt.Sprintf("Protocol-%d", proto)
	}
}

// FormatTCPFlags returns a human-readable TCP flags string
func FormatTCPFlags(flags uint8) string {
	var result string
	if flags&0x01 != 0 { result += "FIN " }
	if flags&0x02 != 0 { result += "SYN " }
	if flags&0x04 != 0 { result += "RST " }
	if flags&0x08 != 0 { result += "PSH " }
	if flags&0x10 != 0 { result += "ACK " }
	if flags&0x20 != 0 { result += "URG " }
	return result
}
