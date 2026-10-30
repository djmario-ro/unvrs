import { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Spinner from "./components/Spinner";

// The public door and login pages stay in the entry chunk (tiny, first paint).
import LoginPage from "./pages/LoginPage";
import DoorPage from "./pages/client/DoorPage";

// The staff app is lazy-loaded, so a guest opening /door on a phone does not
// download the calendar, dashboard, date-fns, etc.
const AppLayout = lazy(() => import("./pages/AppLayout"));
const RequireAdmin = lazy(() => import("./components/RequireAdmin"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const UsersPage = lazy(() => import("./pages/UsersPage"));
const BookingPage = lazy(() => import("./pages/admin/BookingPage"));
const GuestsPage = lazy(() => import("./pages/admin/GuestsPage"));
const AssignmentsPage = lazy(() => import("./pages/admin/AssignmentsPage"));
const RoomsPage = lazy(() => import("./pages/admin/RoomsPage"));
const RoomViewPage = lazy(() => import("./pages/RoomViewPage"));
const WhatsAppPage = lazy(() => import("./pages/admin/WhatsAppPage"));
const AuditPage = lazy(() => import("./pages/admin/AuditPage"));

function Loading() {
  return (
    <div className="flex justify-center py-20">
      <Spinner size={32} />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/door/:roomHash" element={<DoorPage />} />

        {/* Protected staff app */}
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />

          {/* Front desk — any signed-in staff */}
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="booking" element={<BookingPage />} />
          <Route path="guests" element={<GuestsPage />} />
          <Route path="bookings" element={<AssignmentsPage />} />
          <Route path="rooms/:roomId" element={<RoomViewPage />} />

          {/* Property management — admin only */}
          <Route element={<RequireAdmin />}>
            <Route path="rooms" element={<RoomsPage />} />
            <Route path="whatsapp" element={<WhatsAppPage />} />
            <Route path="audit" element={<AuditPage />} />
            <Route path="users" element={<UsersPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/app" replace />} />
      </Routes>
    </Suspense>
  );
}
