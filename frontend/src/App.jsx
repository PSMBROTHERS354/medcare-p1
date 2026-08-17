import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Shell from './components/Shell';
import CommandCenter from './pages/CommandCenter';
import Intelligence from './pages/Intelligence';
import DecisionStudio from './pages/DecisionStudio';
import Monitoring from './pages/Monitoring';
import './pages/CommandCenter.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/intelligence" element={<Intelligence />} />
          <Route path="/decision-studio" element={<DecisionStudio />} />
          <Route path="/monitoring" element={<Monitoring />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
