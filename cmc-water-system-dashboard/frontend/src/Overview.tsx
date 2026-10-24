import {useQuery} from '@tanstack/react-query'
import {Alert,Button,Card,Spin,Statistic} from 'antd'
import dayjs from 'dayjs'
import {api} from './api'

type WaterCard = {code:'WFI'|'PW'|'PS', water_type:string, point_count:number, annual_sample_count:number}
type OverviewResponse = {
  year:number, date_from:string, date_to:string, water_cards:WaterCard[], data_context:any
}

export function Overview({tokenVersion}:{tokenVersion:number}) {
  const overview=useQuery<OverviewResponse>({queryKey:['overview',tokenVersion],queryFn:()=>api('overview')})
  if(overview.isPending) return <Spin/>
  if(overview.error) return <Alert type="error" message={(overview.error as Error).message}
    action={<Button onClick={()=>overview.refetch()}>重试</Button>}/>
  const data=overview.data
  return <>
    <div className="water-overview" aria-label="水系统总览">
      {data.water_cards.map(card=><Card key={card.code} title={<><strong>{card.code}</strong><span className="water-name">{card.water_type}</span></>}>
        <div className="water-counts">
          <Statistic title="点位数" value={card.point_count}/>
          <Statistic title="年度样品总数" value={card.annual_sample_count}/>
        </div>
        <p className="muted">{data.year} 年 · 截至 {dayjs(data.date_to).subtract(1,'day').format('YYYY-MM-DD')}</p>
      </Card>)}
    </div>
    <p className="muted">点位数：全部已有入选数据中的不同内部点位；年度样品总数：今年 1 月 1 日至今天已有入选结果的样品，按样品去重。两项均仅纳入已复核状态。</p>
  </>
}
