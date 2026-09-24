import { useEffect } from 'react'
import { Spin } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { hubLoginUrl } from '@/shared/base'

export default function LoginPage() {
  const [params] = useSearchParams()
  const reason = params.get('reason')

  useEffect(() => {
    const target = new URL(hubLoginUrl(), window.location.origin)
    if (reason) target.searchParams.set('reason', reason)
    window.location.replace(`${target.pathname}${target.search}`)
  }, [reason])

  return <Spin tip="正在返回统一门户登录…"><div style={{ minHeight: 180 }} /></Spin>
}
