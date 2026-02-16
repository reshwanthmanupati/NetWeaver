import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Divider,
  IconButton,
  Stack,
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon } from '@mui/icons-material';
import api from '../services/api';

// ── Constants ──────────────────────────────────────────────────────
const POLICY_TYPES = ['latency', 'bandwidth', 'security', 'routing', 'qos', 'availability'] as const;

const ACTION_TYPES = ['route', 'qos', 'firewall', 'traffic_engineering'] as const;

const CONSTRAINT_METRICS = ['latency', 'bandwidth', 'packet_loss', 'jitter'] as const;
const CONSTRAINT_OPERATORS = ['<', '>', '<=', '>=', '=='] as const;
const CONSTRAINT_UNITS = ['ms', 'Gbps', 'Mbps', '%', 'pps'] as const;

const TARGET_TYPES = ['device', 'interface', 'network', 'region'] as const;

// ── Default form state ─────────────────────────────────────────────
const EMPTY_FORM = {
  name: '',
  description: '',
  priority: 100,
  policyType: 'latency' as string,
  constraintMetric: 'latency' as string,
  constraintOperator: '<' as string,
  constraintValue: '50',
  constraintUnit: 'ms' as string,
  actionType: 'qos' as string,
  targetType: 'device' as string,
  targetIdentifiers: '',
};

// ── Component ──────────────────────────────────────────────────────
const Intents: React.FC = () => {
  const [intents, setIntents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openDialog, setOpenDialog] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  /* extra constraints beyond the primary one */
  const [extraConstraints, setExtraConstraints] = useState<
    { metric: string; operator: string; value: string; unit: string }[]
  >([]);

  /* extra actions beyond the primary one */
  const [extraActions, setExtraActions] = useState<{ type: string }[]>([]);

  // ---- data fetching --------------------------------------------------
  const fetchIntents = async () => {
    try {
      const result = await api.getIntents();
      setIntents(result.intents || []);
      setError('');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load intents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntents();
  }, []);

  // ---- create handler -------------------------------------------------
  const handleCreate = async () => {
    // Build full intent payload the backend expects
    const constraints = [
      {
        metric: form.constraintMetric,
        operator: form.constraintOperator,
        value: form.constraintValue,
        unit: form.constraintUnit,
      },
      ...extraConstraints,
    ];

    const actions = [
      { type: form.actionType, parameters: {} },
      ...extraActions.map((a) => ({ type: a.type, parameters: {} })),
    ];

    const identifiers = form.targetIdentifiers
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      name: form.name,
      description: form.description,
      priority: form.priority,
      policy: {
        type: form.policyType,
        constraints,
        actions,
      },
      targets: [
        {
          type: form.targetType,
          identifiers: identifiers.length > 0 ? identifiers : ['all'],
        },
      ],
    };

    try {
      await api.createIntent(payload);
      setOpenDialog(false);
      setForm({ ...EMPTY_FORM });
      setExtraConstraints([]);
      setExtraActions([]);
      fetchIntents();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create intent');
    }
  };

  // ---- delete handler -------------------------------------------------
  const handleDelete = async (id: string) => {
    if (window.confirm('Are you sure you want to delete this intent?')) {
      try {
        await api.deleteIntent(id);
        fetchIntents();
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to delete intent');
      }
    }
  };

  // ---- helpers --------------------------------------------------------
  const getStatusColor = (status: string) => {
    const colors: Record<string, 'success' | 'warning' | 'error' | 'info'> = {
      deployed: 'success',
      validated: 'success',
      pending: 'warning',
      failed: 'error',
      draft: 'info',
    };
    return colors[status] || 'default';
  };

  const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [key]: e.target.value });

  // ---- loading state --------------------------------------------------
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // ---- render ---------------------------------------------------------
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Intents</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          Create Intent
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Priority</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {intents.map((intent) => (
              <TableRow key={intent.id}>
                <TableCell>{intent.name}</TableCell>
                <TableCell>
                  <Chip label={intent.policy?.type || 'n/a'} size="small" variant="outlined" />
                </TableCell>
                <TableCell>{intent.priority}</TableCell>
                <TableCell>
                  <Chip label={intent.status} color={getStatusColor(intent.status)} size="small" />
                </TableCell>
                <TableCell>
                  {intent.created_at ? new Date(intent.created_at).toLocaleDateString() : '-'}
                </TableCell>
                <TableCell>
                  <Button size="small" color="error" onClick={() => handleDelete(intent.id)}>
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {intents.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  No intents found
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* ─── Create Dialog ────────────────────────────────────────── */}
      <Dialog
        open={openDialog}
        onClose={() => setOpenDialog(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { maxHeight: '85vh' } }}
      >
        <DialogTitle>Create New Intent</DialogTitle>
        <DialogContent dividers>
          {/* ── Basic Info ─────────────────────────────────────── */}
          <Typography variant="subtitle2" sx={{ mb: 1, mt: 1 }}>
            Basic Information
          </Typography>
          <TextField fullWidth label="Name" value={form.name} onChange={set('name')} margin="dense" required />
          <TextField
            fullWidth
            label="Description"
            value={form.description}
            onChange={set('description')}
            margin="dense"
            multiline
            rows={2}
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label="Priority"
              type="number"
              value={form.priority}
              onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 0 })}
              margin="dense"
              sx={{ width: 140 }}
            />
            <TextField
              select
              label="Policy Type"
              value={form.policyType}
              onChange={set('policyType')}
              margin="dense"
              sx={{ minWidth: 180 }}
              required
            >
              {POLICY_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </MenuItem>
              ))}
            </TextField>
          </Stack>

          <Divider sx={{ my: 2 }} />

          {/* ── Constraints ───────────────────────────────────── */}
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Constraints
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField
              select
              label="Metric"
              value={form.constraintMetric}
              onChange={set('constraintMetric')}
              margin="dense"
              sx={{ minWidth: 130 }}
            >
              {CONSTRAINT_METRICS.map((m) => (
                <MenuItem key={m} value={m}>{m}</MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Op"
              value={form.constraintOperator}
              onChange={set('constraintOperator')}
              margin="dense"
              sx={{ width: 80 }}
            >
              {CONSTRAINT_OPERATORS.map((o) => (
                <MenuItem key={o} value={o}>{o}</MenuItem>
              ))}
            </TextField>
            <TextField
              label="Value"
              value={form.constraintValue}
              onChange={set('constraintValue')}
              margin="dense"
              sx={{ width: 100 }}
            />
            <TextField
              select
              label="Unit"
              value={form.constraintUnit}
              onChange={set('constraintUnit')}
              margin="dense"
              sx={{ width: 100 }}
            >
              {CONSTRAINT_UNITS.map((u) => (
                <MenuItem key={u} value={u}>{u}</MenuItem>
              ))}
            </TextField>
          </Stack>

          {extraConstraints.map((ec, idx) => (
            <Stack key={idx} direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
              <TextField
                select label="Metric" value={ec.metric} margin="dense" sx={{ minWidth: 130 }}
                onChange={(e) => {
                  const copy = [...extraConstraints];
                  copy[idx] = { ...copy[idx], metric: e.target.value };
                  setExtraConstraints(copy);
                }}
              >
                {CONSTRAINT_METRICS.map((m) => <MenuItem key={m} value={m}>{m}</MenuItem>)}
              </TextField>
              <TextField
                select label="Op" value={ec.operator} margin="dense" sx={{ width: 80 }}
                onChange={(e) => {
                  const copy = [...extraConstraints];
                  copy[idx] = { ...copy[idx], operator: e.target.value };
                  setExtraConstraints(copy);
                }}
              >
                {CONSTRAINT_OPERATORS.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
              </TextField>
              <TextField
                label="Value" value={ec.value} margin="dense" sx={{ width: 100 }}
                onChange={(e) => {
                  const copy = [...extraConstraints];
                  copy[idx] = { ...copy[idx], value: e.target.value };
                  setExtraConstraints(copy);
                }}
              />
              <TextField
                select label="Unit" value={ec.unit} margin="dense" sx={{ width: 100 }}
                onChange={(e) => {
                  const copy = [...extraConstraints];
                  copy[idx] = { ...copy[idx], unit: e.target.value };
                  setExtraConstraints(copy);
                }}
              >
                {CONSTRAINT_UNITS.map((u) => <MenuItem key={u} value={u}>{u}</MenuItem>)}
              </TextField>
              <IconButton size="small" onClick={() => setExtraConstraints(extraConstraints.filter((_, i) => i !== idx))}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
          <Button
            size="small"
            sx={{ mt: 0.5 }}
            onClick={() =>
              setExtraConstraints([...extraConstraints, { metric: 'bandwidth', operator: '>', value: '1', unit: 'Gbps' }])
            }
          >
            + Add Constraint
          </Button>

          <Divider sx={{ my: 2 }} />

          {/* ── Actions ───────────────────────────────────────── */}
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Actions
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            <TextField
              select
              label="Action Type"
              value={form.actionType}
              onChange={set('actionType')}
              margin="dense"
              sx={{ minWidth: 200 }}
            >
              {ACTION_TYPES.map((a) => (
                <MenuItem key={a} value={a}>
                  {a.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </MenuItem>
              ))}
            </TextField>
          </Stack>

          {extraActions.map((ea, idx) => (
            <Stack key={idx} direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
              <TextField
                select label="Action Type" value={ea.type} margin="dense" sx={{ minWidth: 200 }}
                onChange={(e) => {
                  const copy = [...extraActions];
                  copy[idx] = { ...copy[idx], type: e.target.value };
                  setExtraActions(copy);
                }}
              >
                {ACTION_TYPES.map((a) => (
                  <MenuItem key={a} value={a}>
                    {a.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </MenuItem>
                ))}
              </TextField>
              <IconButton size="small" onClick={() => setExtraActions(extraActions.filter((_, i) => i !== idx))}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
          ))}
          <Button
            size="small"
            sx={{ mt: 0.5 }}
            onClick={() => setExtraActions([...extraActions, { type: 'route' }])}
          >
            + Add Action
          </Button>

          <Divider sx={{ my: 2 }} />

          {/* ── Targets ───────────────────────────────────────── */}
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Targets
          </Typography>
          <Stack direction="row" spacing={2}>
            <TextField
              select
              label="Target Type"
              value={form.targetType}
              onChange={set('targetType')}
              margin="dense"
              sx={{ minWidth: 160 }}
            >
              {TARGET_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              fullWidth
              label="Identifiers (comma-separated)"
              value={form.targetIdentifiers}
              onChange={set('targetIdentifiers')}
              margin="dense"
              placeholder="e.g. router-1, switch-2"
              helperText='Leave empty to target "all"'
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleCreate} variant="contained" disabled={!form.name}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Intents;
