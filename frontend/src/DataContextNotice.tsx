import {Alert} from 'antd'
import dayjs from 'dayjs'

export function DataContextNotice({context}: {context:any}) {
  return <Alert type="warning" showIcon
    message={`${context.environment} · 源结果最大日期 ${context.max_result_at?dayjs(context.max_result_at).format('YYYY-MM-DD'):'无数据'} · 未配置限度`}
    description={`${context.consistency_note}。${context.timestamp_note}。${context.mapping_status}，源导出截止未知。`}/>
}
