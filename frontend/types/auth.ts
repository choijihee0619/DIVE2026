/** backend/app/schemas/auth.py와 1:1 매핑. */
import type { UserRole } from "./enums";

export interface UserPublic {
  user_id: string;
  role: UserRole;
  display_name: string;
  email: string | null;
  created_at: string | null;
  last_login_at: string | null;
}

export interface LoginData {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserPublic;
}

export interface SignupRequest {
  email: string;
  password: string;
  display_name: string;
  role: UserRole;
}

export interface LoginRequest {
  email: string;
  password: string;
}
