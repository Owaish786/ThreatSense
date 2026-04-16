import axios from 'axios';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:5001';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export async function uploadCsv(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/api/predict', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function fetchStats() {
  const response = await api.get('/api/stats');
  return response.data;
}

export async function fetchHealth() {
  const response = await api.get('/api/health');
  return response.data;
}

export async function fetchLogs(limit = 200) {
  const response = await api.get('/api/logs', { params: { limit } });
  return response.data;
}

export async function deleteLog(id) {
  const response = await api.delete(`/api/logs/${id}`);
  return response.data;
}
