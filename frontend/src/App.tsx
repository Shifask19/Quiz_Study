import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Library from './pages/Library'
import Tutor from './pages/Tutor'
import QuizLab from './pages/QuizLab'
import Revision from './pages/Revision'
import Analytics from './pages/Analytics'
import Benchmark from './pages/Benchmark'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="library" element={<Library />} />
          <Route path="tutor" element={<Tutor />} />
          <Route path="quiz" element={<QuizLab />} />
          <Route path="revision" element={<Revision />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="benchmark" element={<Benchmark />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
