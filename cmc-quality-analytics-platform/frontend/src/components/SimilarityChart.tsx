import type { Data, Layout, Shape, Annotations } from 'plotly.js'
import { Alert, Collapse, Table } from 'antd'
import type { SimilarityPanel } from '@/types/similarity'
import SimilarityPlot from './SimilarityPlot'
import { expandLimits, similarityColors, similarityJitter, symmetricLimits } from '@/services/similarityPresentation'

export const formatSimilarity = (value: number | null | undefined) => value == null ? '—' : Number(value.toPrecision(6)).toString()

export default function SimilarityChart({panel,confidenceLevel,tier2Threshold}: {
  panel:SimilarityPanel; confidenceLevel:number; tier2Threshold:number
}) {
  const {reference:ref, comparisons:tests, band}=panel
  const tier2 = tests[0]?.exploratory_statistics.Tier_Level === 'Tier2'
  const all=[ref,...tests], fmt=formatSimilarity
  const compareColors=similarityColors(tests.length), allColors=similarityColors(all.length)
  const comparisonLabels=tests.map(group=>`${ref.line} vs ${group.line}`)
  const allValues=all.flatMap(group=>group.points.map(point=>point.value))
  const differences=tests.flatMap(group=>group.differences).filter((value):value is number=>value!=null)
  const deltaValue=tests.map(group=>group.exploratory_statistics.Delta).find((value):value is number=>typeof value==='number'&&value>0)
  const deltaLines=deltaValue==null?[]:[lineAt(-deltaValue),lineAt(deltaValue)]
  const ciValues=tests.flatMap(group=>[group.exploratory_statistics.ci_lower,group.exploratory_statistics.ci_upper])
    .filter((value):value is number=>typeof value==='number'&&Number.isFinite(value))
  const comparisonRange=symmetricLimits([...tests.map(group=>group.mean_difference??NaN),...ciValues,...(deltaValue==null?[]:[-deltaValue,deltaValue])])
  const differenceRange=symmetricLimits([...differences,...(deltaValue==null?[]:[-deltaValue,deltaValue])])
  const refCiUp=ref.mean!=null&&ref.mean_ci_upper!=null?Math.max(0,ref.mean_ci_upper-ref.mean):0
  const refCiDown=ref.mean!=null&&ref.mean_ci_lower!=null?Math.max(0,ref.mean-ref.mean_ci_lower):0
  const refSpan=ref.mean==null?null:Math.max(refCiUp/0.4*1.12,(ref.sd??0)*2.5,Math.abs(ref.mean)*0.02,0.1)
  const refRange=ref.mean==null||refSpan==null?undefined:[ref.mean-refSpan*0.6,
    Math.max(ref.mean+refSpan*0.4,ref.mean+refCiUp*1.144)] as [number,number]
  const comparePadding=tests.length<=4?0.6:0.4
  const compareAxis={tickmode:'array' as const,tickvals:tests.map((_,i)=>i),ticktext:comparisonLabels,
    range:[-comparePadding,Math.max(0,tests.length-1)+comparePadding]}
  const rawAxis={tickmode:'array' as const,tickvals:all.map((_,i)=>all.length-1-i),ticktext:all.map(group=>group.line),range:[-0.5,all.length-0.5]}
  const bandRadius=ref.mean==null?1:[...allValues,band.lower,band.upper].reduce<number>((radius,value)=>value==null?radius:Math.max(radius,Math.abs(value-ref.mean!)),1e-9)/0.70
  const rangeAnnotations:Partial<Annotations>[]=tests.flatMap((group,index)=>ref.mean==null||group.min==null||group.max==null?[]:[
    {x:group.min-ref.mean,y:index+0.25,text:fmt(group.min-ref.mean),showarrow:false,xanchor:'right',yanchor:'bottom',font:{size:10}},
    {x:group.max-ref.mean,y:index-0.25,text:fmt(group.max-ref.mean),showarrow:false,xanchor:'left',yanchor:'top',font:{size:10}},
  ])
  const bandAnnotations:Partial<Annotations>[]=tests.map((group,index)=>{
    const row=group.exploratory_statistics
    const judged=tier2&&row.Calculation_Status==='ok'&&
      (row.Tier_Judgement==='Similar'||row.Tier_Judgement==='Not Similar')
    const hit=judged&&row.Tier_Judgement==='Similar'
    const ratio=group.band_ratio==null?'无法计算':`${(group.band_ratio*100).toFixed(1)}% (${group.band_hits}/${group.n})`
    return {xref:'paper',x:1.01,yref:'y',y:all.length-2-index,
      text:judged?`${hit?'√':'x'} ${ratio}`:ratio,
      showarrow:false,xanchor:'left',font:{size:10,color:judged?(hit?'#2ca02c':'#d62728'):'#666'}}
  })
  const equivalenceAnnotations:Partial<Annotations>[]=tests.map((group,index)=>{
    const result=group.exploratory_statistics.Equivalent
    const status=result==='Equivalent'?'探索：达到等效界值':result==='Not Equivalent'?'探索：未证实等效':'无法计算'
    return {xref:'paper',x:0.98,yref:'y',y:index+0.30,text:status,showarrow:false,xanchor:'right',yanchor:'bottom',
      bgcolor:'rgba(255,255,255,0.82)',font:{size:10,color:result==='Equivalent'?'#2ca02c':result==='Not Equivalent'?'#d62728':'#666'}}
  })
  function lineAt(x:number,dash:'solid'|'dash'='dash'):Partial<Shape> {
    return {type:'line',xref:'x',yref:'paper',x0:x,x1:x,y0:0,y1:1,line:{color:'#222',width:1,dash}}
  }
  const line=(x:number,dash:'solid'|'dash'='solid')=>lineAt(x,dash)
  const rawTraces=(difference=false,referenceBand=false):Data[] => (difference?tests:all).map((group,index)=>({
    type:'scatter',mode:'markers',name:group.line,
    x:group.points.map(point=>difference?(ref.mean == null?null:point.value-ref.mean):point.value),
    y:group.points.map((point,i)=>(difference?index:all.length-1-index)+similarityJitter(`${group.line}:${point.source_result_id}:${i}`,referenceBand&&index===0?0.04:0.06)),
    customdata:group.points.map(point=>[point.batch_number??'未提供',point.source_result_id??'未提供',group.line]),
    marker:{color:(difference?compareColors:allColors)[index],size:8,opacity:referenceBand&&index===0?0.85:0.9,line:{color:'#000',width:0.5}},
    hovertemplate:`%{customdata[2]}<br>${difference?'相对参比均值的差值':'原始数值'} %{x}<br>批号 %{customdata[0]}<br>来源编号 %{customdata[1]}<extra></extra>`,
  }))
  const chart=(title:string,data:Data[],layout:Partial<Layout>={},note?:string,rows=tests.length)=>
    <SimilarityPlot title={title} data={data} layout={layout} note={note} rows={rows} filename={panel.scope.attribute_name+'_'+title} />
  return <>
    {panel.warnings.map(warning=><Alert key={warning} type="warning" showIcon message={warning} style={{marginBottom:8}} />)}
    <div className="qap-similarity-grid">
      {chart('图0 · 参考均值', [{type:'bar',x:[ref.line],y:[ref.mean],marker:{color:'skyblue',line:{color:'#222',width:0.8}},
        error_y:{type:'data',symmetric:false,array:[refCiUp],arrayminus:[refCiDown],visible:ref.mean_ci_lower!=null&&ref.mean_ci_upper!=null},
        text:[`Mean=${fmt(ref.mean)}<br>SD=${fmt(ref.sd)} · N=${ref.n}`],textposition:'outside',cliponaxis:false}],
        {margin:{l:60,r:20,t:60,b:60},yaxis:{title:{text:panel.scope.unit||'存储原值'},range:refRange,tickfont:{weight:'normal'}}},
        `误差线为参比均值 ${Math.round(confidenceLevel*100)}% CI：[${fmt(ref.mean_ci_lower)}, ${fmt(ref.mean_ci_upper)}]；仅供探索。`,1)}
      {chart('图1 · 等效性探索（均值差与CI）',tests.map((group,index)=>{
        const row=group.exploratory_statistics, difference=group.mean_difference
        const lower=typeof row.ci_lower==='number'?row.ci_lower:null, upper=typeof row.ci_upper==='number'?row.ci_upper:null
        return {type:'bar',orientation:'h',y:[index],x:[difference],marker:{color:compareColors[index],line:{color:'#222',width:0.8}},
          width:0.45,text:[fmt(difference)],textposition:'auto',error_x:{type:'data',symmetric:false,
            array:[upper!=null&&difference!=null?Math.max(0,upper-difference):0],
            arrayminus:[lower!=null&&difference!=null?Math.max(0,difference-lower):0],visible:lower!=null&&upper!=null}}
      }),
        {shapes:[line(0),...deltaLines],annotations:equivalenceAnnotations,margin:{l:75,r:25,t:35,b:60},
          yaxis:compareAxis,xaxis:{title:{text:'比较组均值 − 参比组均值'},range:comparisonRange}},
        `横条为均值差，误差线为 ${Math.round(confidenceLevel*100)}% CI；虚线 ±Δ=${fmt(deltaValue)}。右侧仅为探索性结果，未经批准。`)}
      {chart('图2 · 个体差值散点',rawTraces(true),{shapes:[line(0),...deltaLines],yaxis:compareAxis,xaxis:{title:{text:'每条观察 − 参比均值'},range:differenceRange}},'虚线 ±Δ 为当前探索参数，不是已批准标准。')}
      {chart('图3 · 差值范围条',tests.map((group,index)=>({type:'bar',orientation:'h',
        base:[ref.mean!=null&&group.min!=null?group.min-ref.mean:0],x:[group.min!=null&&group.max!=null&&ref.mean!=null?group.max-group.min:null],y:[index],width:0.45,
        marker:{color:compareColors[index],line:{color:'#000',width:0.8}},name:group.line,hoverinfo:'skip'})),
        {shapes:[line(0),...deltaLines],annotations:rangeAnnotations,yaxis:compareAxis,xaxis:{title:{text:'最小 / 最大观察 − 参比均值'},range:differenceRange}},'范围条不是置信区间；虚线 ±Δ 仅为探索参数。')}
      {chart('图4 · 原始分布',rawTraces(),
        {yaxis:rawAxis,xaxis:{title:{text:panel.scope.unit||'存储原值'},range:expandLimits(allValues,0.33)}},'纵向错开重叠点，横坐标保留原始值。',all.length)}
      {chart('图5 · 参考带（探索）',rawTraces(false,true),{shapes:[...(ref.mean!=null?[line(ref.mean)]:[]),
        ...(band.lower!=null&&band.upper!=null?[{type:'rect' as const,xref:'x' as const,yref:'paper' as const,x0:band.lower,x1:band.upper,y0:0,y1:1,fillcolor:'rgba(31,119,180,0.08)',line:{width:0},layer:'below' as const},line(band.lower,'dash'),line(band.upper,'dash')]:[])],
        annotations:bandAnnotations,margin:{l:75,r:80,t:35,b:60},yaxis:{...rawAxis,range:[-0.4,all.length-0.6],ticktext:all.map((group,index)=>group.line+(index===0?' (Ref)':''))},
        xaxis:{title:{text:panel.scope.unit||'存储原值'},range:ref.mean!=null?[ref.mean-bandRadius,ref.mean+bandRadius]:expandLimits(allValues)}},
        `参比均值 ± ${band.basis==='manual_delta'?`手动 Δ=${fmt(band.half_width)}`:`${band.k}×样本SD`}：[${fmt(band.lower)}, ${fmt(band.upper)}]；${tier2?`仅可计算的 Tier2 显示探索阈值 ${Math.round(tier2Threshold*100)}% 的 √/x。`:'Tier1 只显示描述比例，不作范围判定。'}未经批准。`,all.length)}
    </div>
    <Collapse className="qap-summary" items={[{key:'rows',label:'查看原始观察与来源编号',children:<Table size="small" pagination={{pageSize:20,showSizeChanger:false}} scroll={{x:700}} rowKey="key"
      dataSource={all.flatMap(group=>group.points.map((point,index)=>({...point,line:group.line,key:group.line+':'+index})))}
      columns={[{title:'产线',dataIndex:'line'},{title:'组别',dataIndex:'group_id'},{title:'批号',dataIndex:'batch_number'},{title:'原值',dataIndex:'value',render:fmt},{title:'来源结果编号',dataIndex:'source_result_id'}]} />}]} />
  </>
}
