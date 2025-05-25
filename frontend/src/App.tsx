import { Routes, Route } from 'react-router-dom';
import Library from './pages/Library';
import Reader from './pages/Reader';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Library />} />
      <Route path="/read/:filename" element={<Reader />} />
    </Routes>
  );
}

export default App;
