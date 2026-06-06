import client from "./client";

export interface LoginRequest {
  username: string;
  password: string;
}

export interface User {
  user_id: number;
  username: string;
  full_name?: string;
  roles: string[];
  must_change_password?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export const login = (data: LoginRequest) =>
  client.post<TokenResponse>("/api/auth/login", data);

export const logout = () => client.post("/api/auth/logout");
