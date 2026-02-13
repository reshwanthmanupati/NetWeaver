// Package routing provides network routing optimization algorithms
// Implements Dijkstra, Floyd-Warshall, and custom latency-minimizing algorithms
package routing

import (
	"container/heap"
	"fmt"
	"math"
	"sort"
)

// Edge represents a network link between two nodes
type Edge struct {
	From      string
	To        string
	Latency   float64  // milliseconds
	Bandwidth float64  // Mbps
	Utilization float64 // 0.0 to 1.0
	PacketLoss float64  // 0.0 to 1.0
	Cost      float64  // Computed metric for routing
}

// Graph represents the network topology
type Graph struct {
	Nodes map[string]*Node
	Edges map[string]map[string]*Edge // From -> To -> Edge
}

// Node represents a network device
type Node struct {
	ID       string
	Type     string  // router, switch, etc.
	Location string
}

// Path represents a route through the network
type Path struct {
	Nodes       []string
	TotalCost   float64
	TotalLatency float64
	MinBandwidth float64
	MaxUtilization float64
	Valid       bool
}

// NewGraph creates a new network graph
func NewGraph() *Graph {
	return &Graph{
		Nodes: make(map[string]*Node),
		Edges: make(map[string]map[string]*Edge),
	}
}

// AddNode adds a node to the graph
func (g *Graph) AddNode(id, nodeType, location string) {
	g.Nodes[id] = &Node{
		ID:       id,
		Type:     nodeType,
		Location: location,
	}
}

// AddEdge adds a directed edge to the graph
func (g *Graph) AddEdge(edge Edge) {
	if g.Edges[edge.From] == nil {
		g.Edges[edge.From] = make(map[string]*Edge)
	}
	g.Edges[edge.From][edge.To] = &edge
}

// AddBidirectionalEdge adds edges in both directions
func (g *Graph) AddBidirectionalEdge(from, to string, latency, bandwidth, utilization, packetLoss float64) {
	edge1 := Edge{
		From:        from,
		To:          to,
		Latency:     latency,
		Bandwidth:   bandwidth,
		Utilization: utilization,
		PacketLoss:  packetLoss,
		Cost:        calculateCost(latency, utilization, packetLoss),
	}
	
	edge2 := Edge{
		From:        to,
		To:          from,
		Latency:     latency,
		Bandwidth:   bandwidth,
		Utilization: utilization,
		PacketLoss:  packetLoss,
		Cost:        calculateCost(latency, utilization, packetLoss),
	}
	
	g.AddEdge(edge1)
	g.AddEdge(edge2)
}

// calculateCost computes edge cost based on multiple metrics
// Lower cost is better. Formula weights latency, utilization, and packet loss
func calculateCost(latency, utilization, packetLoss float64) float64 {
	// Weights for each metric (tunable)
	const (
		latencyWeight    = 0.4
		utilizationWeight = 0.4
		packetLossWeight = 0.2
	)
	
	// Normalize metrics to similar scales
	normalizedLatency := latency / 100.0      // Assume max 100ms baseline
	normalizedUtilization := utilization      // Already 0-1
	normalizedPacketLoss := packetLoss * 100  // Amplify packet loss impact
	
	// Penalize high utilization (>80%) more severely
	if utilization > 0.8 {
		normalizedUtilization *= 2.0
	}
	
	cost := (latencyWeight * normalizedLatency) +
	        (utilizationWeight * normalizedUtilization) +
	        (packetLossWeight * normalizedPacketLoss)
	
	// Ensure cost is always positive
	if cost < 0.001 {
		cost = 0.001
	}
	
	return cost
}

// Dijkstra implements Dijkstra's shortest path algorithm
// Returns the shortest path from source to destination based on edge cost
func (g *Graph) Dijkstra(source, destination string) (*Path, error) {
	if _, exists := g.Nodes[source]; !exists {
		return nil, fmt.Errorf("source node %s not found", source)
	}
	if _, exists := g.Nodes[destination]; !exists {
		return nil, fmt.Errorf("destination node %s not found", destination)
	}
	
	// Initialize distances and previous nodes
	distances := make(map[string]float64)
	previous := make(map[string]string)
	visited := make(map[string]bool)
	
	for nodeID := range g.Nodes {
		distances[nodeID] = math.Inf(1)
	}
	distances[source] = 0
	
	// Priority queue for efficient node selection
	pq := &priorityQueue{}
	heap.Init(pq)
	heap.Push(pq, &item{node: source, priority: 0})
	
	for pq.Len() > 0 {
		current := heap.Pop(pq).(*item).node
		
		if visited[current] {
			continue
		}
		visited[current] = true
		
		if current == destination {
			break
		}
		
		// Check all neighbors
		if neighbors, exists := g.Edges[current]; exists {
			for neighbor, edge := range neighbors {
				if visited[neighbor] {
					continue
				}
				
				newDistance := distances[current] + edge.Cost
				
				if newDistance < distances[neighbor] {
					distances[neighbor] = newDistance
					previous[neighbor] = current
					heap.Push(pq, &item{node: neighbor, priority: newDistance})
				}
			}
		}
	}
	
	// Check if path exists
	if math.IsInf(distances[destination], 1) {
		return nil, fmt.Errorf("no path found from %s to %s", source, destination)
	}
	
	// Reconstruct path
	path := g.reconstructPath(previous, source, destination)
	return path, nil
}

// reconstructPath builds the path from previous node map
func (g *Graph) reconstructPath(previous map[string]string, source, destination string) *Path {
	nodes := []string{}
	current := destination
	
	for current != source {
		nodes = append([]string{current}, nodes...)
		current = previous[current]
	}
	nodes = append([]string{source}, nodes...)
	
	// Calculate path metrics
	totalCost := 0.0
	totalLatency := 0.0
	minBandwidth := math.Inf(1)
	maxUtilization := 0.0
	
	for i := 0; i < len(nodes)-1; i++ {
		edge := g.Edges[nodes[i]][nodes[i+1]]
		totalCost += edge.Cost
		totalLatency += edge.Latency
		
		if edge.Bandwidth < minBandwidth {
			minBandwidth = edge.Bandwidth
		}
		if edge.Utilization > maxUtilization {
			maxUtilization = edge.Utilization
		}
	}
	
	return &Path{
		Nodes:          nodes,
		TotalCost:      totalCost,
		TotalLatency:   totalLatency,
		MinBandwidth:   minBandwidth,
		MaxUtilization: maxUtilization,
		Valid:          true,
	}
}

// FindKShortestPaths finds K alternative paths using Yen's algorithm
// Useful for ECMP (Equal-Cost Multi-Path) routing
func (g *Graph) FindKShortestPaths(source, destination string, k int) ([]*Path, error) {
	paths := []*Path{}
	
	// Find first shortest path
	firstPath, err := g.Dijkstra(source, destination)
	if err != nil {
		return nil, err
	}
	paths = append(paths, firstPath)
	
	// Candidate paths
	candidates := []*Path{}
	
	for i := 1; i < k; i++ {
		previousPath := paths[i-1]
		
		// For each node in previous path, find alternatives
		for j := 0; j < len(previousPath.Nodes)-1; j++ {
			spurNode := previousPath.Nodes[j]
			rootPath := previousPath.Nodes[:j+1]
			
			// Create temporary graph without certain edges
			tempGraph := g.copyGraphForYen(paths, rootPath, j)
			
			// Find shortest path from spur node to destination
			spurPath, err := tempGraph.Dijkstra(spurNode, destination)
			if err != nil {
				continue
			}
			
			// Combine root path and spur path
			totalPath := g.combinePaths(rootPath[:len(rootPath)-1], spurPath)
			
			// Check if path already exists
			if !pathExists(candidates, totalPath) && !pathExists(paths, totalPath) {
				candidates = append(candidates, totalPath)
			}
		}
		
		if len(candidates) == 0 {
			break
		}
		
		// Select path with lowest cost
		sort.Slice(candidates, func(i, j int) bool {
			return candidates[i].TotalCost < candidates[j].TotalCost
		})
		
		paths = append(paths, candidates[0])
		candidates = candidates[1:]
	}
	
	return paths, nil
}

// copyGraphForYen creates a copy of graph with specific edges removed
func (g *Graph) copyGraphForYen(existingPaths []*Path, rootPath []string, index int) *Graph {
	newGraph := NewGraph()
	
	// Copy all nodes
	for id, node := range g.Nodes {
		newGraph.AddNode(id, node.Type, node.Location)
	}
	
	// Copy all edges except those to be removed
	for from, neighbors := range g.Edges {
		for to, edge := range neighbors {
			shouldRemove := false
			
			// Remove edges that would create duplicate paths
			for _, path := range existingPaths {
				if index < len(path.Nodes)-1 {
					if pathsSharePrefix(rootPath, path.Nodes, index) {
						if from == path.Nodes[index] && to == path.Nodes[index+1] {
							shouldRemove = true
							break
						}
					}
				}
			}
			
			if !shouldRemove {
				newGraph.AddEdge(*edge)
			}
		}
	}
	
	return newGraph
}

// combinePaths combines root path and spur path
func (g *Graph) combinePaths(rootPath []string, spurPath *Path) *Path {
	combinedNodes := append([]string{}, rootPath...)
	combinedNodes = append(combinedNodes, spurPath.Nodes...)
	
	// Recalculate metrics
	totalCost := 0.0
	totalLatency := 0.0
	minBandwidth := math.Inf(1)
	maxUtilization := 0.0
	
	for i := 0; i < len(combinedNodes)-1; i++ {
		edge := g.Edges[combinedNodes[i]][combinedNodes[i+1]]
		totalCost += edge.Cost
		totalLatency += edge.Latency
		
		if edge.Bandwidth < minBandwidth {
			minBandwidth = edge.Bandwidth
		}
		if edge.Utilization > maxUtilization {
			maxUtilization = edge.Utilization
		}
	}
	
	return &Path{
		Nodes:          combinedNodes,
		TotalCost:      totalCost,
		TotalLatency:   totalLatency,
		MinBandwidth:   minBandwidth,
		MaxUtilization: maxUtilization,
		Valid:          true,
	}
}

// pathsSharePrefix checks if two paths share a common prefix
func pathsSharePrefix(path1, path2 []string, length int) bool {
	if len(path1) < length || len(path2) < length {
		return false
	}
	for i := 0; i < length; i++ {
		if path1[i] != path2[i] {
			return false
		}
	}
	return true
}

// pathExists checks if a path already exists in the list
func pathExists(paths []*Path, newPath *Path) bool {
	for _, path := range paths {
		if pathsEqual(path.Nodes, newPath.Nodes) {
			return true
		}
	}
	return false
}

// pathsEqual checks if two paths are identical
func pathsEqual(path1, path2 []string) bool {
	if len(path1) != len(path2) {
		return false
	}
	for i := range path1 {
		if path1[i] != path2[i] {
			return false
		}
	}
	return true
}

// Priority queue implementation for Dijkstra's algorithm
type item struct {
	node     string
	priority float64
	index    int
}

type priorityQueue []*item

func (pq priorityQueue) Len() int { return len(pq) }

func (pq priorityQueue) Less(i, j int) bool {
	return pq[i].priority < pq[j].priority
}

func (pq priorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].index = i
	pq[j].index = j
}

func (pq *priorityQueue) Push(x interface{}) {
	n := len(*pq)
	item := x.(*item)
	item.index = n
	*pq = append(*pq, item)
}

func (pq *priorityQueue) Pop() interface{} {
	old := *pq
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	*pq = old[0 : n-1]
	return item
}

// OptimizeRouting finds optimal paths for all source-destination pairs
// Returns routing table with best paths
func (g *Graph) OptimizeRouting() (map[string]map[string]*Path, error) {
	routingTable := make(map[string]map[string]*Path)
	
	// Compute shortest paths for all pairs
	for source := range g.Nodes {
		routingTable[source] = make(map[string]*Path)
		
		for destination := range g.Nodes {
			if source == destination {
				continue
			}
			
			path, err := g.Dijkstra(source, destination)
			if err != nil {
				// No path exists, skip
				continue
			}
			
			routingTable[source][destination] = path
		}
	}
	
	return routingTable, nil
}

// PrintPath prints path information
func (p *Path) PrintPath() {
	fmt.Printf("Path: %v\n", p.Nodes)
	fmt.Printf("  Total Cost: %.4f\n", p.TotalCost)
	fmt.Printf("  Total Latency: %.2f ms\n", p.TotalLatency)
	fmt.Printf("  Min Bandwidth: %.2f Mbps\n", p.MinBandwidth)
	fmt.Printf("  Max Utilization: %.2f%%\n", p.MaxUtilization*100)
}
