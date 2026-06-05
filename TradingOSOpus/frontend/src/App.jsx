import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Scanner from './pages/Scanner';
import Decision from './pages/Decision';
import Portfolio from './pages/Portfolio';
import Backtest from './pages/Backtest';
import Signals from './pages/Signals';
import Settings from './pages/Settings';

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/scanner" element={<Scanner />} />
        <Route path="/decision/:ticker" element={<Decision />} />
        <Route path="/decision" element={<Decision />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/signals" element={<Signals />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}