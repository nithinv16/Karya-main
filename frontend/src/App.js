import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AuthCallback from "@/pages/AuthCallback";
import Login from "@/pages/Login";
import AppLayout from "@/components/AppLayout";
import Dashboard from "@/pages/Dashboard";
import Workforce from "@/pages/Workforce";
import Payroll from "@/pages/Payroll";
import Subcontractors from "@/pages/Subcontractors";
import Compliance from "@/pages/Compliance";
import BureaucracyFeed from "@/pages/BureaucracyFeed";
import Sops from "@/pages/Sops";
import Knowledge from "@/pages/Knowledge";
import Insights from "@/pages/Insights";
import DailyReports from "@/pages/DailyReports";
import Onboarding from "@/pages/Onboarding";
import Profile from "@/pages/Profile";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-3 h-3 bg-[#EA580C] pulse-dot" />
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  if (user.profile_complete === false) return <Navigate to="/onboarding" replace />;
  return children;
}

function OnboardingGuard({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen" />;
  if (!user) return <Navigate to="/" replace />;
  if (user.profile_complete) return <Navigate to="/dashboard" replace />;
  return children;
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen" />;
  if (user && user.profile_complete === false) return <Navigate to="/onboarding" replace />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <Login />;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route
        path="/onboarding"
        element={
          <OnboardingGuard>
            <Onboarding />
          </OnboardingGuard>
        }
      />
      <Route
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/workforce" element={<Workforce />} />
        <Route path="/payroll" element={<Payroll />} />
        <Route path="/subcontractors" element={<Subcontractors />} />
        <Route path="/reports" element={<DailyReports />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/feed" element={<BureaucracyFeed />} />
        <Route path="/sops" element={<Sops />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Toaster position="top-right" theme="light" />
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
