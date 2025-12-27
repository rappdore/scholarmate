import { Routes, Route } from 'react-router-dom';
import Library from './pages/Library';
import Reader from './pages/Reader';
import Statistics from './pages/Statistics';
import Header from './components/Header';

function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <Header />
      <div className="pt-16">
        {' '}
        {/* Add padding to account for fixed header */}
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/read/:documentId" element={<Reader />} />
          <Route path="/statistics/:documentId" element={<Statistics />} />
        </Routes>
      </div>
    </div>
  );
}

export default App;
