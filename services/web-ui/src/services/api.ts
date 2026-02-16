import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || '/api/v1';

interface LoginCredentials {
  username: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── CSRF Token Utility ─────────────────────────────────────────────────────
function getCsrfTokenFromCookie(): string | null {
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrf_token') {
      return value;
    }
  }
  return null;
}

// ── API Service ────────────────────────────────────────────────────────────
class ApiService {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      withCredentials: true, // Enable cookies for CSRF protection
    });

    // Security Note: localStorage for tokens is vulnerable to XSS attacks.
    // In production, prefer httpOnly cookies for token storage.
    // Current implementation maintains backward compatibility.
    this.token = localStorage.getItem('access_token');
    if (this.token) {
      this.setAuthHeader(this.token);
    }

    // Request interceptor - add CSRF token to all state-changing requests
    this.client.interceptors.request.use(
      (config) => {
        // Add CSRF token for POST, PUT, DELETE, PATCH requests
        if (config.method && ['post', 'put', 'delete', 'patch'].includes(config.method.toLowerCase())) {
          const csrfToken = getCsrfTokenFromCookie();
          if (csrfToken) {
            config.headers['X-CSRF-Token'] = csrfToken;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401) {
          // Token expired, redirect to login
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  private setAuthHeader(token: string) {
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/auth/login', credentials);
    this.token = response.data.access_token;
    localStorage.setItem('access_token', this.token);
    this.setAuthHeader(this.token);
    return response.data;
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  logout() {
    this.token = null;
    localStorage.removeItem('access_token');
    delete this.client.defaults.headers.common['Authorization'];
  }

  // Dashboard
  async getDashboard() {
    const response = await this.client.get('/dashboard');
    return response.data;
  }

  // Intents
  async getIntents(params?: any) {
    const response = await this.client.get('/intents', { params });
    return response.data;
  }

  async getIntent(id: string) {
    const response = await this.client.get(`/intents/${id}`);
    return response.data;
  }

  async createIntent(intent: any) {
    const response = await this.client.post('/intents', intent);
    return response.data;
  }

  async deleteIntent(id: string) {
    await this.client.delete(`/intents/${id}`);
  }

  async deployIntent(id: string, config: any) {
    const response = await this.client.post(`/intents/${id}/deploy`, config);
    return response.data;
  }

  // Devices
  async getDevices(params?: any) {
    const response = await this.client.get('/devices', { params });
    return response.data;
  }

  async getDevice(id: string) {
    const response = await this.client.get(`/devices/${id}`);
    return response.data;
  }

  async registerDevice(device: any) {
    const response = await this.client.post('/devices', device);
    return response.data;
  }

  async deployConfig(id: string, config: any) {
    const response = await this.client.post(`/devices/${id}/config`, config);
    return response.data;
  }

  // Incidents
  async getIncidents(params?: any) {
    const response = await this.client.get('/incidents', { params });
    return response.data;
  }

  async getIncident(id: string) {
    const response = await this.client.get(`/incidents/${id}`);
    return response.data;
  }

  async resolveIncident(id: string, resolution: any) {
    const response = await this.client.post(`/incidents/${id}/resolve`, resolution);
    return response.data;
  }

  async getMTTR(period?: string) {
    const response = await this.client.get('/incidents/stats/mttr', {
      params: { period },
    });
    return response.data;
  }

  // Threats
  async getThreats(params?: any) {
    const response = await this.client.get('/threats', { params });
    return response.data;
  }

  async getThreat(id: string) {
    const response = await this.client.get(`/threats/${id}`);
    return response.data;
  }

  async mitigateThreat(config: any) {
    const response = await this.client.post('/mitigate', config);
    return response.data;
  }

  async getSecurityStats() {
    const response = await this.client.get('/security/stats');
    return response.data;
  }

  isAuthenticated(): boolean {
    return this.token !== null;
  }
}

export const api = new ApiService();
export default api;
