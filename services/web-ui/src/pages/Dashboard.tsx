import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Description as IntentsIcon,
  Devices as DevicesIcon,
  Warning as IncidentsIcon,
  Security as ThreatsIcon,
} from '@mui/icons-material';
import api from '../services/api';

interface DashboardData {
  timestamp: string;
  data: {
    intents?: { total: number; intents: any[] };
    devices?: { total: number; online: number; error?: string };
    incidents?: { total_incidents: number; by_status: any; by_severity: any };
    threats?: { total_threats: number; active_threats: number; critical_threats: number };
  };
}

const StatCard: React.FC<{
  title: string;
  value: number;
  subtitle?: string;
  icon: React.ReactElement;
  color: string;
}> = ({ title, value, subtitle, icon, color }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography color="text.secondary" gutterBottom variant="overline">
            {title}
          </Typography>
          <Typography variant="h3" component="div">
            {value}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            backgroundColor: color,
            borderRadius: 2,
            p: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {React.cloneElement(icon, { sx: { color: 'white', fontSize: 32 } })}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

const Dashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        const result = await api.getDashboard();
        setData(result);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
    const interval = setInterval(fetchDashboard, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        Last updated: {data ? new Date(data.timestamp).toLocaleString() : '-'}
      </Typography>

      <Grid container spacing={3} sx={{ mt: 2 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Intents"
            value={data?.data.intents?.total || 0}
            subtitle={`${data?.data.intents?.intents.filter((i: any) => i.status === 'deployed').length || 0} deployed`}
            icon={<IntentsIcon />}
            color="#2196f3"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Devices"
            value={data?.data.devices?.total || 0}
            subtitle={data?.data.devices?.error ? 'Error loading' : `${data?.data.devices?.online || 0} online`}
            icon={<DevicesIcon />}
            color="#4caf50"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Incidents"
            value={data?.data.incidents?.total_incidents || 0}
            subtitle={`${data?.data.incidents?.by_status?.detected || 0} active`}
            icon={<IncidentsIcon />}
            color="#ff9800"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Threats"
            value={data?.data.threats?.total_threats || 0}
            subtitle={`${data?.data.threats?.active_threats || 0} active, ${data?.data.threats?.critical_threats || 0} critical`}
            icon={<ThreatsIcon />}
            color="#f44336"
          />
        </Grid>
      </Grid>

      {/* Recent Intents */}
      {data?.data.intents && data.data.intents.intents.length > 0 && (
        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            Recent Intents
          </Typography>
          <Grid container spacing={2}>
            {data.data.intents.intents.slice(0, 3).map((intent: any) => (
              <Grid item xs={12} key={intent.id}>
                <Card>
                  <CardContent>
                    <Typography variant="h6">{intent.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {intent.description}
                    </Typography>
                    <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                      Status: {intent.status} | Priority: {intent.priority}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default Dashboard;
