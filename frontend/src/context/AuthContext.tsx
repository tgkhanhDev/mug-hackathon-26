import { createContext } from 'react';

export interface AuthContextType {
  userId: string | null;
  sessionId: string | null;
  isAuthenticated: boolean;
  openAuthModal: () => void;
}

export const AuthContext = createContext<AuthContextType>({
  userId: null,
  sessionId: null,
  isAuthenticated: false,
  openAuthModal: () => {},
});
