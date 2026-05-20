import { useContext } from "react";
import { AuthContext } from "@/contexts/auth-context";

/**
 * Provides access to the current auth state and auth actions.
 * Must be used inside an <AuthProvider>.
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
