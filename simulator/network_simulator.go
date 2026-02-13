// Network Simulator for NetWeaver Testing
// Simulates a 100-node network with realistic traffic patterns
package main

import (
	"fmt"
	"math/rand"
	"time"

	"github.com/netweaver/netweaver/pkg/routing"
)

// NetworkSimulator simulates a network topology with traffic
type NetworkSimulator struct {
	Graph     *routing.Graph
	NumNodes  int
	Topology  string // "mesh", "ring", "tree", "random"
	BaseLatency float64
	BaseBandwidth float64
}

// NewNetworkSimulator creates a new network simulator
func NewNetworkSimulator(numNodes int, topology string) *NetworkSimulator {
	return &NetworkSimulator{
		Graph:         routing.NewGraph(),
		NumNodes:      numNodes,
		Topology:      topology,
		BaseLatency:   5.0,   // 5ms base latency
		BaseBandwidth: 10000, // 10 Gbps
	}
}

// GenerateTopology creates the network topology
func (ns *NetworkSimulator) GenerateTopology() {
	fmt.Printf("Generating %s topology with %d nodes...\n", ns.Topology, ns.NumNodes)
	
	// Add nodes
	for i := 0; i < ns.NumNodes; i++ {
		nodeID := fmt.Sprintf("R%d", i)
		nodeType := "router"
		location := fmt.Sprintf("DC-%d", i/20) // 20 nodes per datacenter
		ns.Graph.AddNode(nodeID, nodeType, location)
	}
	
	// Create links based on topology type
	switch ns.Topology {
	case "mesh":
		ns.generateMeshTopology()
	case "ring":
		ns.generateRingTopology()
	case "tree":
		ns.generateTreeTopology()
	case "random":
		ns.generateRandomTopology()
	default:
		ns.generateRandomTopology()
	}
	
	fmt.Printf("Generated topology with %d nodes and %d edges\n", 
		len(ns.Graph.Nodes), ns.countEdges())
}

// generateMeshTopology creates a mesh network (every node connected to nearby nodes)
func (ns *NetworkSimulator) generateMeshTopology() {
	// Partial mesh - each node connected to ~5 neighbors for scalability
	neighborsPerNode := 5
	
	for i := 0; i < ns.NumNodes; i++ {
		nodeID := fmt.Sprintf("R%d", i)
		
		// Connect to next N neighbors (circular)
		for j := 1; j <= neighborsPerNode; j++ {
			neighborIdx := (i + j) % ns.NumNodes
			neighborID := fmt.Sprintf("R%d", neighborIdx)
			
			if !ns.edgeExists(nodeID, neighborID) {
				latency := ns.BaseLatency + rand.Float64()*10
				bandwidth := ns.BaseBandwidth * (0.5 + rand.Float64()*0.5)
				utilization := rand.Float64() * 0.6 // 0-60% utilization
				packetLoss := rand.Float64() * 0.001 // 0-0.1% packet loss
				
				ns.Graph.AddBidirectionalEdge(nodeID, neighborID, latency, bandwidth, utilization, packetLoss)
			}
		}
	}
}

// generateRingTopology creates a ring network
func (ns *NetworkSimulator) generateRingTopology() {
	for i := 0; i < ns.NumNodes; i++ {
		nodeID := fmt.Sprintf("R%d", i)
		nextID := fmt.Sprintf("R%d", (i+1)%ns.NumNodes)
		
		latency := ns.BaseLatency + rand.Float64()*5
		bandwidth := ns.BaseBandwidth
		utilization := rand.Float64() * 0.5
		packetLoss := rand.Float64() * 0.0005
		
		ns.Graph.AddBidirectionalEdge(nodeID, nextID, latency, bandwidth, utilization, packetLoss)
	}
}

// generateTreeTopology creates a hierarchical tree network
func (ns *NetworkSimulator) generateTreeTopology() {
	// 3-level tree: core, distribution, access
	coreNodes := 5
	distNodes := 20
	_ = ns.NumNodes - coreNodes - distNodes // accessNodes
	
	// Core layer - fully meshed
	for i := 0; i < coreNodes; i++ {
		for j := i + 1; j < coreNodes; j++ {
			nodeID1 := fmt.Sprintf("R%d", i)
			nodeID2 := fmt.Sprintf("R%d", j)
			
			ns.Graph.AddBidirectionalEdge(nodeID1, nodeID2, 
				ns.BaseLatency, ns.BaseBandwidth, rand.Float64()*0.4, 0.0001)
		}
	}
	
	// Distribution layer - connect to core
	for i := coreNodes; i < coreNodes+distNodes; i++ {
		nodeID := fmt.Sprintf("R%d", i)
		// Connect to 2 core nodes
		core1 := fmt.Sprintf("R%d", i%coreNodes)
		core2 := fmt.Sprintf("R%d", (i+1)%coreNodes)
		
		ns.Graph.AddBidirectionalEdge(nodeID, core1,
			ns.BaseLatency+2, ns.BaseBandwidth*0.8, rand.Float64()*0.5, 0.0002)
		ns.Graph.AddBidirectionalEdge(nodeID, core2,
			ns.BaseLatency+2, ns.BaseBandwidth*0.8, rand.Float64()*0.5, 0.0002)
	}
	
	// Access layer - connect to distribution
	for i := coreNodes + distNodes; i < ns.NumNodes; i++ {
		nodeID := fmt.Sprintf("R%d", i)
		distNode := fmt.Sprintf("R%d", coreNodes+((i-coreNodes-distNodes)%distNodes))
		
		ns.Graph.AddBidirectionalEdge(nodeID, distNode,
			ns.BaseLatency+5, ns.BaseBandwidth*0.4, rand.Float64()*0.7, 0.0005)
	}
}

// generateRandomTopology creates a random network with realistic characteristics
func (ns *NetworkSimulator) generateRandomTopology() {
	rand.Seed(time.Now().UnixNano())
	
	// Ensure connectivity: create a spanning tree first
	for i := 1; i < ns.NumNodes; i++ {
		nodeID := fmt.Sprintf("R%d", i)
		// Connect to random previous node
		parentIdx := rand.Intn(i)
		parentID := fmt.Sprintf("R%d", parentIdx)
		
		latency := ns.BaseLatency + rand.Float64()*15
		bandwidth := ns.BaseBandwidth * (0.3 + rand.Float64()*0.7)
		utilization := rand.Float64() * 0.6
		packetLoss := rand.Float64() * 0.002
		
		ns.Graph.AddBidirectionalEdge(nodeID, parentID, latency, bandwidth, utilization, packetLoss)
	}
	
	// Add random extra links for redundancy (average degree ~3-4)
	extraLinks := ns.NumNodes * 2
	for i := 0; i < extraLinks; i++ {
		node1 := fmt.Sprintf("R%d", rand.Intn(ns.NumNodes))
		node2 := fmt.Sprintf("R%d", rand.Intn(ns.NumNodes))
		
		if node1 != node2 && !ns.edgeExists(node1, node2) {
			latency := ns.BaseLatency + rand.Float64()*20
			bandwidth := ns.BaseBandwidth * (0.3 + rand.Float64()*0.7)
			utilization := rand.Float64() * 0.7
			packetLoss := rand.Float64() * 0.003
			
			ns.Graph.AddBidirectionalEdge(node1, node2, latency, bandwidth, utilization, packetLoss)
		}
	}
}

// edgeExists checks if an edge already exists
func (ns *NetworkSimulator) edgeExists(from, to string) bool {
	if edges, exists := ns.Graph.Edges[from]; exists {
		if _, exists := edges[to]; exists {
			return true
		}
	}
	return false
}

// countEdges counts the number of edges in the graph
func (ns *NetworkSimulator) countEdges() int {
	count := 0
	for _, edges := range ns.Graph.Edges {
		count += len(edges)
	}
	return count / 2 // Bidirectional, so divide by 2
}

// SimulateTraffic simulates traffic patterns and updates link metrics
func (ns *NetworkSimulator) SimulateTraffic(duration time.Duration) {
	fmt.Printf("\nSimulating traffic for %v...\n", duration)
	
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	
	timeout := time.After(duration)
	iteration := 0
	
	for {
		select {
		case <-ticker.C:
			iteration++
			ns.updateLinkMetrics(iteration)
			fmt.Printf("  Iteration %d: Updated link metrics\n", iteration)
			
		case <-timeout:
			fmt.Println("Traffic simulation complete")
			return
		}
	}
}

// updateLinkMetrics updates link utilization and latency based on traffic patterns
func (ns *NetworkSimulator) updateLinkMetrics(iteration int) {
	// Simulate time-of-day patterns
	hour := (iteration * 5 / 60) % 24
	isPeakHour := (hour >= 9 && hour <= 17)
	
	for from, neighbors := range ns.Graph.Edges {
		for to, edge := range neighbors {
			// Base utilization varies by time of day
			baseUtil := 0.3
			if isPeakHour {
				baseUtil = 0.6
			}
			
			// Add random variation
			edge.Utilization = baseUtil + (rand.Float64()-0.5)*0.2
			if edge.Utilization < 0 {
				edge.Utilization = 0
			}
			if edge.Utilization > 1.0 {
				edge.Utilization = 1.0
			}
			
			// Latency increases with utilization (queueing delay)
			utilizationFactor := 1.0 + edge.Utilization*2
			edge.Latency = ns.BaseLatency * utilizationFactor
			
			// Packet loss increases with utilization
			if edge.Utilization > 0.8 {
				edge.PacketLoss = 0.001 + (edge.Utilization-0.8)*0.01
			} else {
				edge.PacketLoss = 0.0001 * rand.Float64()
			}
			
			// Recalculate cost
			edge.Cost = calculateCost(edge.Latency, edge.Utilization, edge.PacketLoss)
			
			ns.Graph.Edges[from][to] = edge
		}
	}
}

// calculateCost computes edge cost based on multiple metrics
func calculateCost(latency, utilization, packetLoss float64) float64 {
	const (
		latencyWeight    = 0.4
		utilizationWeight = 0.4
		packetLossWeight = 0.2
	)
	
	normalizedLatency := latency / 100.0
	normalizedUtilization := utilization
	normalizedPacketLoss := packetLoss * 100
	
	if utilization > 0.8 {
		normalizedUtilization *= 2.0
	}
	
	cost := (latencyWeight * normalizedLatency) +
	        (utilizationWeight * normalizedUtilization) +
	        (packetLossWeight * normalizedPacketLoss)
	
	if cost < 0.001 {
		cost = 0.001
	}
	
	return cost
}

// BenchmarkRouting benchmarks the routing algorithm
func (ns *NetworkSimulator) BenchmarkRouting() {
	fmt.Println("\n=== Routing Benchmark ===")
	
	// Test routing from R0 to R99
	source := "R0"
	destination := fmt.Sprintf("R%d", ns.NumNodes-1)
	
	// Single path
	start := time.Now()
	path, err := ns.Graph.Dijkstra(source, destination)
	elapsed := time.Since(start)
	
	if err != nil {
		fmt.Printf("Error finding path: %v\n", err)
		return
	}
	
	fmt.Printf("\nShortest path from %s to %s:\n", source, destination)
	path.PrintPath()
	fmt.Printf("Computation time: %v\n", elapsed)
	
	// K shortest paths
	k := 3
	start = time.Now()
	paths, err := ns.Graph.FindKShortestPaths(source, destination, k)
	elapsed = time.Since(start)
	
	if err != nil {
		fmt.Printf("Error finding K paths: %v\n", err)
		return
	}
	
	fmt.Printf("\nTop %d paths from %s to %s:\n", k, source, destination)
	for i, p := range paths {
		fmt.Printf("\nPath %d:\n", i+1)
		p.PrintPath()
	}
	fmt.Printf("Computation time for %d paths: %v\n", k, elapsed)
	
	// Full routing table optimization
	fmt.Println("\nComputing full routing table...")
	start = time.Now()
	routingTable, err := ns.Graph.OptimizeRouting()
	elapsed = time.Since(start)
	
	if err != nil {
		fmt.Printf("Error optimizing routing: %v\n", err)
		return
	}
	
	pathCount := 0
	for _, destinations := range routingTable {
		pathCount += len(destinations)
	}
	
	fmt.Printf("Computed %d paths in %v\n", pathCount, elapsed)
	fmt.Printf("Average time per path: %v\n", elapsed/time.Duration(pathCount))
}

// PrintStatistics prints network statistics
func (ns *NetworkSimulator) PrintStatistics() {
	fmt.Println("\n=== Network Statistics ===")
	fmt.Printf("Nodes: %d\n", len(ns.Graph.Nodes))
	fmt.Printf("Edges: %d\n", ns.countEdges())
	
	// Calculate average metrics
	totalLatency := 0.0
	totalUtil := 0.0
	totalPacketLoss := 0.0
	edgeCount := 0
	
	for _, neighbors := range ns.Graph.Edges {
		for _, edge := range neighbors {
			totalLatency += edge.Latency
			totalUtil += edge.Utilization
			totalPacketLoss += edge.PacketLoss
			edgeCount++
		}
	}
	
	if edgeCount > 0 {
		fmt.Printf("Average Latency: %.2f ms\n", totalLatency/float64(edgeCount))
		fmt.Printf("Average Utilization: %.2f%%\n", (totalUtil/float64(edgeCount))*100)
		fmt.Printf("Average Packet Loss: %.4f%%\n", (totalPacketLoss/float64(edgeCount))*100)
	}
}

func main() {
	fmt.Println("=== NetWeaver Network Simulator ===\n")
	
	// Create 100-node network
	simulator := NewNetworkSimulator(100, "random")
	
	// Generate topology
	simulator.GenerateTopology()
	
	// Print initial statistics
	simulator.PrintStatistics()
	
	// Benchmark routing algorithms
	simulator.BenchmarkRouting()
	
	// Simulate traffic (comment out for quick testing)
	// simulator.SimulateTraffic(30 * time.Second)
	
	// Re-run benchmark after traffic changes
	// simulator.BenchmarkRouting()
	
	fmt.Println("\n=== Simulation Complete ===")
}
