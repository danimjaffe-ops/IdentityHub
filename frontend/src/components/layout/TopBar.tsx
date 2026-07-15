import { useAuth } from "../../hooks/useAuth";
import { Button } from "../ui/Button";

export function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-end px-6">
      {user && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{user.email}</span>
          <Button variant="secondary" size="sm" onClick={logout}>
            Log out
          </Button>
        </div>
      )}
    </header>
  );
}
