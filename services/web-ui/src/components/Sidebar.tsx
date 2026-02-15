import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Box,
  Divider,
  IconButton,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Description as IntentsIcon,
  Devices as DevicesIcon,
  Warning as IncidentsIcon,
  Security as ThreatsIcon,
  AccountTree as TopologyIcon,
  Logout as LogoutIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const drawerWidth = 240;

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { text: 'Intents', icon: <IntentsIcon />, path: '/intents' },
  { text: 'Devices', icon: <DevicesIcon />, path: '/devices' },
  { text: 'Incidents', icon: <IncidentsIcon />, path: '/incidents' },
  { text: 'Threats', icon: <ThreatsIcon />, path: '/threats' },
  { text: 'Topology', icon: <TopologyIcon />, path: '/topology' },
];

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Drawer
      variant="permanent"
      sx={{
        width: drawerWidth,
        flexShrink: 0,
        '& .MuiDrawer-paper': {
          width: drawerWidth,
          boxSizing: 'border-box',
        },
      }}
    >
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          NetWeaver
        </Typography>
      </Toolbar>
      <Divider />
      <Box sx={{ overflow: 'auto', flexGrow: 1 }}>
        <List>
          {menuItems.map((item) => (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => navigate(item.path)}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
      </Box>
      <Divider />
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" display="block" gutterBottom>
          {user?.username}
        </Typography>
        <IconButton onClick={handleLogout} size="small">
          <LogoutIcon />
          <Typography variant="caption" sx={{ ml: 1 }}>
            Logout
          </Typography>
        </IconButton>
      </Box>
    </Drawer>
  );
};

export default Sidebar;
