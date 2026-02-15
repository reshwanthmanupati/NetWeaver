# NetWeaver Web UI

React + TypeScript frontend for NetWeaver Intent-Based Network Management platform.

## Features

- **Dashboard**: Real-time system overview with statistics from all services
- **Intent Management**: Create, view, and deploy network intents
- **Device Management**: Register and monitor network devices
- **Incident Monitoring**: View and resolve network incidents with MTTR tracking
- **Security Threats**: Monitor and mitigate DDoS attacks and security threats
- **Network Topology**: Visual representation of network devices and connections

## Tech Stack

- **React 18** with TypeScript
- **Material-UI (MUI)** for components
- **React Router** for navigation
- **Axios** for API calls
- **Chart.js & Recharts** for data visualization
- **Cytoscape.js** for network topology (planned)

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Start development server (proxies to API Gateway on port 8080)
npm start

# Open http://localhost:3000
```

### Production Build

```bash
# Build for production
npm run build

# Serve with nginx or any static file server
```

### Docker

```bash
# Build image
docker build -t netweaver-web-ui .

# Run container
docker run -d -p 3000:80 --name netweaver-ui netweaver-web-ui
```

## Configuration

### API Endpoint

The application proxies API requests to the API Gateway. Configure the proxy in `package.json`:

```json
{
  "proxy": "http://localhost:8080"
}
```

For production, update the nginx configuration in `nginx.conf` to point to your API Gateway.

### Environment Variables

Create a `.env` file in the root directory:

```env
REACT_APP_API_URL=http://localhost:8080/api/v1
REACT_APP_WS_URL=ws://localhost:8080/ws
```

## Authentication

The UI uses JWT-based authentication:

1. Login with credentials (demo: `admin` / `admin123`)
2. Token is stored in localStorage
3. Token is automatically included in API requests
4. Expired tokens trigger automatic logout

## Project Structure

```
src/
├── components/          # Reusable UI components
│   └── Sidebar.tsx     # Navigation sidebar
├── contexts/           # React contexts
│   └── AuthContext.tsx # Authentication state management
├── pages/              # Page components
│   ├── Dashboard.tsx   # System overview
│   ├── Intents.tsx     # Intent management
│   ├── Devices.tsx     # Device management
│   ├── Incidents.tsx   # Incident monitoring
│   ├── Threats.tsx     # Security threats
│   ├── Topology.tsx    # Network visualization
│   └── Login.tsx       # Login page
├── services/           # API service layer
│   └── api.ts          # API client with auth
├── App.tsx             # Main application component
└── index.tsx           # Application entry point
```

## Available Scripts

- `npm start` - Start development server
- `npm run build` - Build for production
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App

## API Integration

The UI integrates with the NetWeaver API Gateway which provides:

- `/api/v1/auth/*` - Authentication endpoints
- `/api/v1/intents/*` - Intent management
- `/api/v1/devices/*` - Device management
- `/api/v1/incidents/*` - Incident monitoring
- `/api/v1/threats/*` - Security monitoring
- `/api/v1/dashboard` - Aggregated dashboard data
- `/ws` - WebSocket for real-time updates

## Features by Page

### Dashboard
- Real-time statistics from all services
- Intent count and deployment status
- Device health and connectivity
- Active incidents and MTTR
- Current security threats

### Intents
- List all network intents
- Create new intents
- Deploy intents to devices
- Delete intents
- View intent details and status

### Devices
- List registered devices
- Register new devices (Cisco, Juniper, Arista)
- View device status and health
- Device credentials management

### Incidents
- List all network incidents
- View incident details and remediation actions
- Manual incident resolution
- MTTR statistics
- Incident filtering by status and severity

### Threats
- List detected security threats
- Threat severity and status
- Deploy mitigation strategies (blackhole, rate limit, ACL, WAF)
- Security statistics and trends

### Topology
- Network device visualization (planned)
- Device relationships and connections
- Link status and health
- Interactive graph exploration

## Future Enhancements

- [ ] Real-time WebSocket updates
- [ ] Interactive network topology with Cytoscape.js
- [ ] Advanced intent YAML editor with syntax highlighting
- [ ] Configuration diff viewer
- [ ] Historical charts for incidents and threats
- [ ] Dark/light theme toggle
- [ ] User management
- [ ] Role-based access control
- [ ] Notification center
- [ ] Export reports (PDF/CSV)

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

Copyright © 2026 NetWeaver Project
