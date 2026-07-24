import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { HelmetProvider } from "react-helmet-async";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { I18nProvider } from "@/lib/i18n";
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
import Help from "@/pages/Help";
import Expenses from "@/pages/Expenses";
import { BlogIndex, BlogPost } from "@/pages/Blog";
import Contact from "@/pages/Contact";
import Attendance from "@/pages/Attendance";
import Pricing from "@/pages/Pricing";

function Protected({ children, allowIncomplete = false }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-3 h-3 bg-[#EA580C] pulse-dot" />
      </div>
    );
  }
  if (!user) return <Navigate to="/" replace />;
  if (!allowIncomplete && user.profile_complete === false) return <Navigate to="/onboarding" replace />;
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
      <Route path="/:locale" element={<Home />} />
      <Route path="/blog" element={<BlogIndex />} />
      <Route path="/:locale/blog" element={<BlogIndex />} />
      <Route path="/blog/:slug" element={<BlogPost />} />
      <Route path="/:locale/blog/:slug" element={<BlogPost />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/:locale/contact" element={<Contact />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/:locale/pricing" element={<Pricing />} />
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
          <Protected allowIncomplete>
            <AppLayout />
          </Protected>
        }
      >
        <Route path="/profile" element={<Profile />} />
      </Route>
      <Route
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/workforce" element={<Workforce />} />
        <Route path="/attendance" element={<Attendance />} />
        <Route path="/payroll" element={<Payroll />} />
        <Route path="/subcontractors" element={<Subcontractors />} />
        <Route path="/reports" element={<DailyReports />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/feed" element={<BureaucracyFeed />} />
        <Route path="/sops" element={<Sops />} />
        <Route path="/knowledge" element={<Knowledge />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/expenses" element={<Expenses />} />
        <Route path="/help" element={<Help />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function I18nBinder({ children }) {
  const { user } = useAuth();
  return <I18nProvider userLang={user?.language}>{children}</I18nProvider>;
}

function App() {
  return (
    <div className="App">
      <HelmetProvider>
        <BrowserRouter>
          <AuthProvider>
            <I18nBinder>
              <Toaster position="top-right" theme="light" />
              <AppRouter />
            </I18nBinder>
          </AuthProvider>
        </BrowserRouter>
      </HelmetProvider>
    </div>
  );
}

export default App;
