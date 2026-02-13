// Package sflow provides sFlow v5 packet parsing
// sFlow is an industry standard for monitoring high-speed switched networks
package sflow

import (
	"encoding/binary"
	"fmt"
	"net"
	"time"
)

// sFlow version constant
const (
	SFlowVersion5 = 5
)

// Enterprise format constants
const (
	EnterpriseStandard = 0
)

// Sample format constants
const (
	SampleFlowSample = 1
	SampleCounterSample = 2
	SampleFlowSampleExpanded = 3
	SampleCounterSampleExpanded = 4
)

// Flow data format constants
const (
	FlowRawPacketHeader = 1
	FlowEthernetFrame = 2
	FlowIPv4 = 3
	FlowIPv6 = 4
	FlowExtendedSwitch = 1001
	FlowExtendedRouter = 1002
)

// FlowRecord represents a parsed sFlow flow record
type FlowRecord struct {
	Timestamp       time.Time
	AgentIP         net.IP
	SourceIP        net.IP
	DestinationIP   net.IP
	SourcePort      uint16
	DestPort        uint16
	Protocol        uint8
	Bytes           uint64
	Packets         uint64
	InputInterface  uint32
	OutputInterface uint32
	SamplingRate    uint32
	PacketSize      uint32
	EtherType       uint16
	VlanID          uint16
}

// SFlowHeader represents the sFlow datagram header
type SFlowHeader struct {
	Version        uint32 // sFlow version (5)
	AddressType    uint32 // 1 = IPv4, 2 = IPv6
	AgentAddress   net.IP
	SubAgentID     uint32
	SequenceNumber uint32
	Uptime         uint32 // Milliseconds since device boot
	NumSamples     uint32
}

// SampleHeader represents a sample record header
type SampleHeader struct {
	Format     uint32 // Enterprise | Format
	Length     uint32
	Enterprise uint32 // Extracted from Format
	SampleType uint32 // Extracted from Format
}

// FlowSample represents a flow sample record
type FlowSample struct {
	SequenceNumber  uint32
	SourceID        uint32 // Source interface index
	SamplingRate    uint32
	SamplePool      uint32
	Drops           uint32
	InputInterface  uint32
	OutputInterface uint32
	NumRecords      uint32
}

// Parser handles parsing of sFlow packets
type Parser struct {
	// Statistics
	PacketsParsed uint64
	RecordsParsed uint64
	ParseErrors   uint64
}

// NewParser creates a new sFlow parser
func NewParser() *Parser {
	return &Parser{}
}

// Parse parses an sFlow datagram and returns flow records
func (p *Parser) Parse(data []byte) ([]FlowRecord, error) {
	if len(data) < 28 {
		p.ParseErrors++
		return nil, fmt.Errorf("sFlow packet too short: %d bytes", len(data))
	}

	offset := 0

	// Parse datagram header
	version := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4

	if version != SFlowVersion5 {
		p.ParseErrors++
		return nil, fmt.Errorf("unsupported sFlow version: %d", version)
	}

	addressType := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4

	var agentIP net.IP
	if addressType == 1 { // IPv4
		if len(data) < offset+4 {
			p.ParseErrors++
			return nil, fmt.Errorf("packet too short for IPv4 agent address")
		}
		agentIP = net.IP(data[offset:offset+4])
		offset += 4
	} else if addressType == 2 { // IPv6
		if len(data) < offset+16 {
			p.ParseErrors++
			return nil, fmt.Errorf("packet too short for IPv6 agent address")
		}
		agentIP = net.IP(data[offset:offset+16])
		offset += 16
	} else {
		p.ParseErrors++
		return nil, fmt.Errorf("invalid address type: %d", addressType)
	}

	subAgentID := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	sequenceNumber := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	uptime := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	numSamples := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4

	_ = subAgentID
	_ = sequenceNumber

	// Parse samples
	flows := make([]FlowRecord, 0, numSamples)
	timestamp := time.Now()

	for i := uint32(0); i < numSamples; i++ {
		if offset+8 > len(data) {
			break
		}

		// Parse sample header
		sampleFormat := binary.BigEndian.Uint32(data[offset:offset+4])
		offset += 4
		sampleLength := binary.BigEndian.Uint32(data[offset:offset+4])
		offset += 4

		// Extract enterprise and format
		enterprise := (sampleFormat >> 12) & 0xFFFFF
		format := sampleFormat & 0xFFF

		if offset+int(sampleLength) > len(data) {
			p.ParseErrors++
			break
		}

		sampleData := data[offset:offset+int(sampleLength)]

		// Parse based on sample type
		if enterprise == EnterpriseStandard && (format == SampleFlowSample || format == SampleFlowSampleExpanded) {
			sampleFlows, err := p.parseFlowSample(sampleData, agentIP, timestamp, uptime)
			if err == nil {
				flows = append(flows, sampleFlows...)
			}
		}

		offset += int(sampleLength)
	}

	p.PacketsParsed++
	p.RecordsParsed += uint64(len(flows))

	return flows, nil
}

// parseFlowSample parses a flow sample
func (p *Parser) parseFlowSample(data []byte, agentIP net.IP, timestamp time.Time, uptime uint32) ([]FlowRecord, error) {
	if len(data) < 32 {
		return nil, fmt.Errorf("flow sample too short")
	}

	offset := 0

	sequenceNumber := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	sourceID := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	samplingRate := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	samplePool := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	drops := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	inputInterface := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	outputInterface := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	numRecords := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4

	_ = sequenceNumber
	_ = sourceID
	_ = samplePool
	_ = drops

	flows := make([]FlowRecord, 0, numRecords)

	// Parse flow records
	for i := uint32(0); i < numRecords; i++ {
		if offset+8 > len(data) {
			break
		}

		recordFormat := binary.BigEndian.Uint32(data[offset:offset+4])
		offset += 4
		recordLength := binary.BigEndian.Uint32(data[offset:offset+4])
		offset += 4

		if offset+int(recordLength) > len(data) {
			break
		}

		recordData := data[offset:offset+int(recordLength)]
		
		// Extract enterprise and format
		enterprise := (recordFormat >> 12) & 0xFFFFF
		format := recordFormat & 0xFFF

		// Parse raw packet header
		if enterprise == EnterpriseStandard && format == FlowRawPacketHeader {
			flow := p.parseRawPacketHeader(recordData, agentIP, timestamp, inputInterface, outputInterface, samplingRate)
			if flow != nil {
				flows = append(flows, *flow)
			}
		}

		offset += int(recordLength)
	}

	return flows, nil
}

// parseRawPacketHeader parses a raw packet header flow record
func (p *Parser) parseRawPacketHeader(data []byte, agentIP net.IP, timestamp time.Time, 
	inputIface, outputIface, samplingRate uint32) *FlowRecord {
	
	if len(data) < 16 {
		return nil
	}

	offset := 0

	protocol := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	frameLength := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	stripped := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4
	headerLength := binary.BigEndian.Uint32(data[offset:offset+4])
	offset += 4

	_ = stripped

	if offset+int(headerLength) > len(data) {
		return nil
	}

	headerData := data[offset:offset+int(headerLength)]

	// Parse Ethernet header (14 bytes minimum)
	if len(headerData) < 14 {
		return nil
	}

	// Skip MAC addresses (12 bytes)
	etherType := binary.BigEndian.Uint16(headerData[12:14])
	ipOffset := 14

	// Handle VLAN tags (0x8100)
	var vlanID uint16
	if etherType == 0x8100 {
		if len(headerData) < ipOffset+4 {
			return nil
		}
		vlanID = binary.BigEndian.Uint16(headerData[ipOffset:ipOffset+2]) & 0x0FFF
		etherType = binary.BigEndian.Uint16(headerData[ipOffset+2:ipOffset+4])
		ipOffset += 4
	}

	// Parse IPv4 packet (0x0800)
	if etherType == 0x0800 {
		if len(headerData) < ipOffset+20 {
			return nil
		}

		ipHeader := headerData[ipOffset:]
		
		// IP version and header length
		versionIHL := ipHeader[0]
		ihl := (versionIHL & 0x0F) * 4
		
		if len(ipHeader) < int(ihl) {
			return nil
		}

		// Parse IP header fields
		tos := ipHeader[1]
		totalLength := binary.BigEndian.Uint16(ipHeader[2:4])
		protocol := ipHeader[9]
		srcIP := net.IP(ipHeader[12:16])
		dstIP := net.IP(ipHeader[16:20])

		_ = tos
		_ = totalLength

		// Parse transport layer (TCP/UDP)
		var srcPort, dstPort uint16
		if int(ihl)+4 <= len(ipHeader) {
			transportHeader := ipHeader[ihl:]
			srcPort = binary.BigEndian.Uint16(transportHeader[0:2])
			dstPort = binary.BigEndian.Uint16(transportHeader[2:4])
		}

		// Create flow record
		flow := &FlowRecord{
			Timestamp:       timestamp,
			AgentIP:         agentIP,
			SourceIP:        srcIP,
			DestinationIP:   dstIP,
			SourcePort:      srcPort,
			DestPort:        dstPort,
			Protocol:        protocol,
			Bytes:           uint64(frameLength) * uint64(samplingRate),
			Packets:         uint64(samplingRate), // One packet sampled
			InputInterface:  inputIface,
			OutputInterface: outputIface,
			SamplingRate:    samplingRate,
			PacketSize:      frameLength,
			EtherType:       etherType,
			VlanID:          vlanID,
		}

		return flow
	}

	// IPv6 and other protocols not implemented in this basic version
	_ = protocol
	return nil
}

// GetStatistics returns parser statistics
func (p *Parser) GetStatistics() (packets, records, errors uint64) {
	return p.PacketsParsed, p.RecordsParsed, p.ParseErrors
}
