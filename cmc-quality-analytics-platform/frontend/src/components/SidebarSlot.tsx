import { createContext, useContext, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export const SidebarHost = createContext<HTMLElement | null>(null)

export function SidebarSlot({ children }: { children: ReactNode }) {
  const host = useContext(SidebarHost)
  return host ? createPortal(children, host) : null
}
