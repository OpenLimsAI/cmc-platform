export interface AuthStatus {
  auth_required: boolean
  configured: boolean
}

export interface QapIdentity {
  username: string
  full_name: string | null
  subject: string
  roles: string[]
  can_read: boolean
  can_preview: boolean
  can_commit: false
}
