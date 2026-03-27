import { Routes, Route, NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Brain, Users, Settings, Calendar,
  TrendingUp, DollarSign, Activity, Shield, Banknote, Key, LogOut
} from 'lucide-react'

import Dashboard from './pages/Dashboard'
import MemoryBrowser from './pages/MemoryBrowser'
import PeopleCRM from './pages/PeopleCRM'
import CalendarView from './pages/CalendarView'
import TradeJournal from './pages/TradeJournal'
import CostTracker from './pages/CostTracker'
import ActionLog from './pages/ActionLog'
import EarningsPage from './pages/EarningsPage'
import SettingsPage from './pages/SettingsPage'
import SetupPage from './pages/SetupPage'
import LoginPage from './pages/LoginPage'
import { logout } from './api/client'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/memory', icon: Brain, label: 'Memory' },
  { to: '/people', icon: Users, label: 'People' },
  { to: '/trades', icon: TrendingUp, label: 'Trades' },
  { to: '/earnings', icon: Banknote, label: 'Earnings' },
  { to: '/costs', icon: DollarSign, label: 'Costs' },
  { to: '/actions', icon: Activity, label: 'Actions' },
  { to: '/setup', icon: Key, label: 'Setup' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

function MainLayout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <nav className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-2xl font-bold text-mira-500">MIRA</h1>
          <p className="text-xs text-gray-500 mt-1">Autonomous Digital Twin</p>
        </div>

        <div className="flex-1 py-4">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-6 py-3 text-sm transition-colors ${
                  isActive
                    ? 'text-mira-400 bg-mira-500/10 border-r-2 border-mira-500'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </div>

        <div className="p-4 border-t border-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-gray-600">
              <Shield size={14} />
              <span>Kill Switch: /killswitch</span>
            </div>
            <button
              onClick={logout}
              className="text-gray-600 hover:text-red-400 transition-colors"
              title="Logout"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-gray-950 p-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/calendar" element={<CalendarView />} />
          <Route path="/memory" element={<MemoryBrowser />} />
          <Route path="/people" element={<PeopleCRM />} />
          <Route path="/trades" element={<TradeJournal />} />
          <Route path="/earnings" element={<EarningsPage />} />
          <Route path="/costs" element={<CostTracker />} />
          <Route path="/actions" element={<ActionLog />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/*" element={<MainLayout />} />
    </Routes>
  )
}
