import axios from 'axios';

const API = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
});

export const fetchDecision = (ticker, capital = 500000000) =>
  API.get(`/decision/${ticker}`, { params: { capital } });

export const fetchSignals = (ticker) => API.get(`/signals/${ticker}`);
export const fetchData = (ticker, start = '2020-01-01') =>
  API.get(`/data/${ticker}`, { params: { start } });
export const fetchBacktest = (ticker, strategy = '1W') =>
  API.get(`/backtest/${ticker}`, { params: { strategy } });
export const fetchPortfolio = () => API.get('/portfolio');
export const trainModel = (ticker, horizon = '1W') =>
  API.post(`/train/${ticker}`, null, { params: { horizon } });

export default API;