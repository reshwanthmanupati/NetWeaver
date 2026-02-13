// Unit tests for NetFlow parser
package netflow

import (
	"net"
	"testing"
	"time"
)

func TestNetFlowV5Parser(t *testing.T) {
	parser := NewParser()
	
	// Create a minimal valid NetFlow v5 packet
	// Header (24 bytes) + 1 flow record (48 bytes) = 72 bytes
	packet := make([]byte, 72)
	
	// Header
	packet[0] = 0x00 // Version high byte
	packet[1] = 0x05 // Version low byte (NetFlow v5)
	packet[2] = 0x00 // Count high byte
	packet[3] = 0x01 // Count low byte (1 record)
	
	// SysUptime (4 bytes)
	packet[4] = 0x00
	packet[5] = 0x00
	packet[6] = 0x00
	packet[7] = 0x64 // 100 ms
	
	// Unix timestamp (8 bytes for secs + nsecs)
	now := uint32(time.Now().Unix())
	packet[8] = byte(now >> 24)
	packet[9] = byte(now >> 16)
	packet[10] = byte(now >> 8)
	packet[11] = byte(now)
	
	// Flow record starts at byte 24
	recordOffset := 24
	
	// Source IP: 192.168.1.10
	packet[recordOffset+0] = 192
	packet[recordOffset+1] = 168
	packet[recordOffset+2] = 1
	packet[recordOffset+3] = 10
	
	// Destination IP: 10.0.0.50
	packet[recordOffset+4] = 10
	packet[recordOffset+5] = 0
	packet[recordOffset+6] = 0
	packet[recordOffset+7] = 50
	
	// Source port: 443
	packet[recordOffset+32] = 0x01
	packet[recordOffset+33] = 0xBB
	
	// Dest port: 54321
	packet[recordOffset+34] = 0xD4
	packet[recordOffset+35] = 0x31
	
	// Protocol: TCP (6)
	packet[recordOffset+38] = 6
	
	// Packets: 100
	packet[recordOffset+16] = 0x00
	packet[recordOffset+17] = 0x00
	packet[recordOffset+18] = 0x00
	packet[recordOffset+19] = 0x64
	
	// Bytes: 150000
	packet[recordOffset+20] = 0x00
	packet[recordOffset+21] = 0x02
	packet[recordOffset+22] = 0x49
	packet[recordOffset+23] = 0xF0
	
	exporterIP := net.ParseIP("192.168.1.1")
	
	flows, err := parser.Parse(packet, exporterIP)
	
	if err != nil {
		t.Fatalf("Failed to parse NetFlow v5 packet: %v", err)
	}
	
	if len(flows) != 1 {
		t.Fatalf("Expected 1 flow, got %d", len(flows))
	}
	
	flow := flows[0]
	
	// Verify parsed data
	if flow.SourceIP.String() != "192.168.1.10" {
		t.Errorf("Expected source IP 192.168.1.10, got %s", flow.SourceIP)
	}
	
	if flow.DestinationIP.String() != "10.0.0.50" {
		t.Errorf("Expected destination IP 10.0.0.50, got %s", flow.DestinationIP)
	}
	
	if flow.SourcePort != 443 {
		t.Errorf("Expected source port 443, got %d", flow.SourcePort)
	}
	
	if flow.DestPort != 54321 {
		t.Errorf("Expected dest port 54321, got %d", flow.DestPort)
	}
	
	if flow.Protocol != 6 {
		t.Errorf("Expected protocol TCP (6), got %d", flow.Protocol)
	}
	
	if flow.Packets != 100 {
		t.Errorf("Expected 100 packets, got %d", flow.Packets)
	}
	
	if flow.Bytes != 150000 {
		t.Errorf("Expected 150000 bytes, got %d", flow.Bytes)
	}
}

func TestNetFlowParserInvalidVersion(t *testing.T) {
	parser := NewParser()
	
	// Create packet with unsupported version
	packet := make([]byte, 24)
	packet[0] = 0x00
	packet[1] = 0xFF // Invalid version
	
	exporterIP := net.ParseIP("192.168.1.1")
	
	_, err := parser.Parse(packet, exporterIP)
	
	if err == nil {
		t.Fatal("Expected error for invalid version, got nil")
	}
}

func TestNetFlowParserTooShort(t *testing.T) {
	parser := NewParser()
	
	// Create packet that's too short
	packet := make([]byte, 10)
	
	exporterIP := net.ParseIP("192.168.1.1")
	
	_, err := parser.Parse(packet, exporterIP)
	
	if err == nil {
		t.Fatal("Expected error for short packet, got nil")
	}
}

func TestFormatProtocol(t *testing.T) {
	tests := []struct {
		proto    uint8
		expected string
	}{
		{ProtocolICMP, "ICMP"},
		{ProtocolTCP, "TCP"},
		{ProtocolUDP, "UDP"},
		{47, "Protocol-47"}, // GRE
	}
	
	for _, test := range tests {
		result := FormatProtocol(test.proto)
		if result != test.expected {
			t.Errorf("FormatProtocol(%d) = %s, expected %s", test.proto, result, test.expected)
		}
	}
}

func TestFormatTCPFlags(t *testing.T) {
	tests := []struct {
		flags    uint8
		contains []string
	}{
		{0x02, []string{"SYN"}},
		{0x12, []string{"SYN", "ACK"}},
		{0x01, []string{"FIN"}},
	}
	
	for _, test := range tests {
		result := FormatTCPFlags(test.flags)
		for _, expected := range test.contains {
			if len(result) == 0 || !contains(result, expected) {
				t.Errorf("FormatTCPFlags(0x%02X) = '%s', expected to contain '%s'", 
					test.flags, result, expected)
			}
		}
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && 
		(s[:len(substr)] == substr || s[len(s)-len(substr):] == substr || 
		 hasSubstring(s, substr)))
}

func hasSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func BenchmarkNetFlowV5Parse(b *testing.B) {
	parser := NewParser()
	
	// Create a packet with 30 flows (typical NetFlow v5 packet size)
	numFlows := 30
	packet := make([]byte, 24+48*numFlows)
	
	// Header
	packet[0] = 0x00
	packet[1] = 0x05
	packet[2] = byte(numFlows >> 8)
	packet[3] = byte(numFlows)
	
	// Fill in minimal flow data
	for i := 0; i < numFlows; i++ {
		offset := 24 + i*48
		// Set some basic fields to make it valid
		packet[offset+38] = 6 // TCP protocol
	}
	
	exporterIP := net.ParseIP("192.168.1.1")
	
	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		_, _ = parser.Parse(packet, exporterIP)
	}
}
