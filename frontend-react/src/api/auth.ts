import { mdmLogin, mdmLogout, type MdmLoginResult, type MdmUser } from "../shared/cmabSession";

export interface LoginRequest {
  username: string;
  password: string;
}

// = MDM 登录响应里的 user 对象（全公司统一落 localStorage['cmab_user']）
export type User = MdmUser;
export type TokenResponse = MdmLoginResult;

// 2026-09-04 起登录/登出直接打 MDM（同源 /mdm/api/v1），refresh Cookie 落在 MDM 路径下，
// 后续续期由 shared/cmabSession 统一处理；后端 /api/auth/login 代理保留仅供脚本/旧客户端。
export const login = (data: LoginRequest): Promise<TokenResponse> =>
  mdmLogin(data.username.trim(), data.password);

export const logout = (): Promise<void> => mdmLogout();
