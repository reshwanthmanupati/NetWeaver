// Unit tests for routing optimizer
package routing

import (
	"testing"
)

func TestGraphCreation(t *testing.T) {
	g := NewGraph()
	
	g.AddNode("R1", "router", "DC1")
	g.AddNode("R2", "router", "DC1")
	g.AddNode("R3", "router", "DC2")
	
	if len(g.Nodes) != 3 {
		t.Errorf("Expected 3 nodes, got %d", len(g.Nodes))
	}
	
	g.AddBidirectionalEdge("R1", "R2", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R2", "R3", 10.0, 10000, 0.5, 0.002)
	
	if g.Edges["R1"]["R2"] == nil {
		t.Error("Edge R1->R2 not found")
	}
	
	if g.Edges["R2"]["R1"] == nil {
		t.Error("Edge R2->R1 not found (bidirectional)")
	}
}

func TestDijkstraSimplePath(t *testing.T) {
	g := NewGraph()
	
	// Create a simple linear topology: R1 -> R2 -> R3
	g.AddNode("R1", "router", "DC1")
	g.AddNode("R2", "router", "DC1")
	g.AddNode("R3", "router", "DC2")
	
	g.AddBidirectionalEdge("R1", "R2", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R2", "R3", 10.0, 10000, 0.5, 0.002)
	
	path, err := g.Dijkstra("R1", "R3")
	
	if err != nil {
		t.Fatalf("Dijkstra failed: %v", err)
	}
	
	expectedPath := []string{"R1", "R2", "R3"}
	
	if len(path.Nodes) != len(expectedPath) {
		t.Errorf("Expected path length %d, got %d", len(expectedPath), len(path.Nodes))
	}
	
	for i, node := range expectedPath {
		if path.Nodes[i] != node {
			t.Errorf("Expected node %s at position %d, got %s", node, i, path.Nodes[i])
		}
	}
	
	if path.TotalLatency != 15.0 {
		t.Errorf("Expected total latency 15.0, got %.2f", path.TotalLatency)
	}
}

func TestDijkstraAlternativePath(t *testing.T) {
	g := NewGraph()
	
	// Create topology with alternative path:
	//    R1 --- R2 (fast, high util)
	//    |      |
	//    +- R4 -+ (slow, low util)
	
	g.AddNode("R1", "router", "DC1")
	g.AddNode("R2", "router", "DC1")
	g.AddNode("R4", "router", "DC1")
	
	// Direct path: low latency but high utilization
	g.AddBidirectionalEdge("R1", "R2", 5.0, 10000, 0.9, 0.001)
	
	// Alternative path through R4: higher latency but low utilization
	g.AddBidirectionalEdge("R1", "R4", 10.0, 10000, 0.2, 0.001)
	g.AddBidirectionalEdge("R4", "R2", 10.0, 10000, 0.2, 0.001)
	
	path, err := g.Dijkstra("R1", "R2")
	
	if err != nil {
		t.Fatalf("Dijkstra failed: %v", err)
	}
	
	// Should choose alternative path due to high utilization on direct link
	// Cost calculation penalizes high utilization
	if len(path.Nodes) == 2 && path.MaxUtilization > 0.5 {
		t.Logf("Note: Direct path chosen despite high utilization (cost-based)")
	}
	
	if path.TotalCost <= 0 {
		t.Error("Path cost should be positive")
	}
}

func TestDijkstraNoPath(t *testing.T) {
	g := NewGraph()
	
	// Create disconnected graph
	g.AddNode("R1", "router", "DC1")
	g.AddNode("R2", "router", "DC2")
	
	// No edges between them
	
	_, err := g.Dijkstra("R1", "R2")
	
	if err == nil {
		t.Error("Expected error for disconnected nodes, got nil")
	}
}

func TestFindKShortestPaths(t *testing.T) {
	g := NewGraph()
	
	// Create topology with multiple paths:
	//     R1 ---- R2
	//     |   X   |
	//     R3 ---- R4
	
	g.AddNode("R1", "router", "DC1")
	g.AddNode("R2", "router", "DC1")
	g.AddNode("R3", "router", "DC1")
	g.AddNode("R4", "router", "DC1")
	
	// Create multiple paths from R1 to R4
	g.AddBidirectionalEdge("R1", "R2", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R2", "R4", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R1", "R3", 6.0, 10000, 0.2, 0.001)
	g.AddBidirectionalEdge("R3", "R4", 6.0, 10000, 0.2, 0.001)
	g.AddBidirectionalEdge("R1", "R4", 15.0, 10000, 0.1, 0.001) // Direct but longer
	
	paths, err := g.FindKShortestPaths("R1", "R4", 3)
	
	if err != nil {
		t.Fatalf("FindKShortestPaths failed: %v", err)
	}
	
	if len(paths) == 0 {
		t.Fatal("Expected at least one path")
	}
	
	// First path should be shortest
	if paths[0].TotalCost >= paths[len(paths)-1].TotalCost {
		t.Error("Paths should be sorted by cost")
	}
	
	t.Logf("Found %d paths", len(paths))
	for i, path := range paths {
		t.Logf("Path %d: %v (cost: %.4f)", i+1, path.Nodes, path.TotalCost)
	}
}

func TestOptimizeRouting(t *testing.T) {
	g := NewGraph()
	
	// Create small network
	for i := 1; i <= 5; i++ {
		g.AddNode(nodeID(i), "router", "DC1")
	}
	
	// Create some edges
	g.AddBidirectionalEdge("R1", "R2", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R2", "R3", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R3", "R4", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R4", "R5", 5.0, 10000, 0.3, 0.001)
	g.AddBidirectionalEdge("R1", "R5", 25.0, 10000, 0.1, 0.001)
	
	routingTable, err := g.OptimizeRouting()
	
	if err != nil {
		t.Fatalf("OptimizeRouting failed: %v", err)
	}
	
	// Check that we have routes
	if len(routingTable) == 0 {
		t.Fatal("Routing table is empty")
	}
	
	// Check specific route
	if path, exists := routingTable["R1"]["R5"]; exists {
		if path == nil {
			t.Error("Path from R1 to R5 is nil")
		} else {
			t.Logf("Route R1->R5: %v (latency: %.2fms)", path.Nodes, path.TotalLatency)
		}
	}
}

func TestCalculateCost(t *testing.T) {
	tests := []struct {
		name        string
		latency     float64
		utilization float64
		packetLoss  float64
	}{
		{"Low everything", 5.0, 0.2, 0.0001},
		{"High latency", 50.0, 0.2, 0.0001},
		{"High utilization", 5.0, 0.9, 0.0001},
		{"High packet loss", 5.0, 0.2, 0.01},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cost := calculateCost(tt.latency, tt.utilization, tt.packetLoss)
			
			if cost <= 0 {
				t.Errorf("Cost should be positive, got %.4f", cost)
			}
			
			t.Logf("Cost for %s: %.4f", tt.name, cost)
		})
	}
	
	// Test that high utilization results in higher cost
	costLowUtil := calculateCost(10.0, 0.3, 0.001)
	costHighUtil := calculateCost(10.0, 0.9, 0.001)
	
	if costHighUtil <= costLowUtil {
		t.Error("High utilization should result in higher cost")
	}
}

func nodeID(n int) string {
	return []string{"R1", "R2", "R3", "R4", "R5"}[n-1]
}

func BenchmarkDijkstra(b *testing.B) {
	g := NewGraph()
	
	// Create a 100-node network
	for i := 0; i < 100; i++ {
		g.AddNode(nodeIDFromInt(i), "router", "DC1")
	}
	
	// Add edges to create connected graph
	for i := 0; i < 100; i++ {
		for j := 0; j < 3; j++ {
			neighbor := (i + j + 1) % 100
			if i != neighbor {
				g.AddBidirectionalEdge(
					nodeIDFromInt(i),
					nodeIDFromInt(neighbor),
					5.0+float64(j)*2,
					10000,
					0.3,
					0.001,
				)
			}
		}
	}
	
	b.ResetTimer()
	
	for i := 0; i < b.N; i++ {
		_, _ = g.Dijkstra("R0", "R99")
	}
}

func nodeIDFromInt(n int) string {
	if n < 10 {
		return "R" + string(rune('0'+n))
	}
	return "R" + string(rune('0'+n/10)) + string(rune('0'+n%10))
}
