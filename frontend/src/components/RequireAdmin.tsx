import RequireRoles from "./RequireRoles";
import { MANAGERS } from "../lib/access";
export default function RequireAdmin() {
  return <RequireRoles roles={MANAGERS} />;
}
