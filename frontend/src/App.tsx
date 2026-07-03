import { Routes, Route, Navigate } from "react-router-dom";
import AdminLayout from "./pages/admin/AdminLayout";
import GuestsPage from "./pages/admin/GuestsPage";
import RoomsPage from "./pages/admin/RoomsPage";
import AssignmentsPage from "./pages/admin/AssignmentsPage";
import AuditPage from "./pages/admin/AuditPage";
import DoorPage from "./pages/client/DoorPage";

export default function App() {
  return (
    <Routes>
      {/* Door client — opened via QR code */}
      <Route path="/door/:roomId" element={<DoorPage />} />

      {/* Admin panel */}
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Navigate to="guests" replace />} />
        <Route path="guests" element={<GuestsPage />} />
        <Route path="rooms" element={<RoomsPage />} />
        <Route path="assignments" element={<AssignmentsPage />} />
        <Route path="audit" element={<AuditPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}
