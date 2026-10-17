import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { SystemStatusResponse } from '../api/types';

interface AuthContextType {
  token: string | null;
  tenant: SystemStatusResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (readToken: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // CRITICAL SECURITY INVARIANT:
  // Token is stored in React memory state ONLY.
  // Never stored in localStorage, sessionStorage, cookies, or VITE_* env vars.
  const [token, setToken] = useState<string | null>(null);
  const [tenant, setTenant] = useState<SystemStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (readToken: string): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/system/status', {
        headers: {
          'Authorization': `Bearer ${readToken.trim()}`,
        },
      });

      if (!res.ok) {
        if (res.status === 401) {
          setError('Invalid tenant read token. Ensure the token is at least 32 characters and registered.');
        } else {
          setError(`Authentication failed with status ${res.status}.`);
        }
        return false;
      }

      const data: SystemStatusResponse = await res.json();
      setToken(readToken.trim());
      setTenant(data);
      return true;
    } catch {
      setError('Cannot connect to REBOOTX backend. Ensure FastAPI server is running on :8000.');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setTenant(null);
    setError(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        token,
        tenant,
        isAuthenticated: !!token && !!tenant,
        isLoading,
        error,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

