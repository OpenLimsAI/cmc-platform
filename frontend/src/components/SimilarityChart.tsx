import type { Data, Layout, Shape, Annotations } from 'plotly.js'
import { Alert, Collapse, Table } from 'antd'
import type { SimilarityPanel } from '@/types/similarity'
import SimilarityPlot from './SimilarityPlot'
import { expandLimits, similarityColors, similarityJitter, symmetricLimits } from '@/services/similarityPresentation'

export const formatSimilarity = (value: number | null | undefined) => value == null ? '—' : Number(value.toPrecision(6)).toString()

export default function SimilarityChart({panel}: {panel:SimilarityPanel}) {
  const {reference:ref, comparisons:tests, band}=panel
  const all=[ref,...tests], fmt=formatSimilarity
  const compareColors=similarityColors(tests.length), allColors=similarityColors(all.length)
  const comparisonLabels=tests.map(group=>`${ref.line} vs ${group.line}`)
  const allValues=all.flatMap(group=>group.points.map(point=>point.value))
  const differences=tests.flatMap(group=>group.differences).filter((value):value is number=>value!=null)
  const comparePadding=tests.length<=4?0.6:0.4
  const compareAxis={tickmode:'array' as const,tickvals:tests.map((_,i)=>i),ticktext:comparisonLabels,
    range:[-comparePadding,Math.max(0,tests.length-1)+comparePadding]}
  const rawAxis={tickmode:'array' as const,tickvals:all.map((_,i)=>all.length-1-i),ticktext:all.map(group=>group.line),range:[-0.5,all.length-0.5]}
  const bandRadius=ref.mean==null?1:[...allValues,band.lower,band.upper].reduce<number>((radius,value)=>value==null?radius:Math.max(radius,Math.abs(value-ref.mean!)),1e-9)/0.70
  const rangeAnnotations:Partial<Annotations>[]=tests.flatMap((group,index)=>ref.mean==null||group.min==null||group.max==null?[]:[
    {x:group.min-ref.mean,y:index+0.25,text:fmt(group.min-ref.mean),showarrow:false,xanchor:'left',yanchor:'bottom',font:{size:10}},
    {x:group.max-ref.mean,y:index-0.25,text:fmt(group.max-ref.mean),showarrow:false,xanchor:'right',yanchor:'top',font:{size:10}},
  ])
  const bandAnnotations:Partial<Annotations>[]=tests.map((group,index)=>({xref:'paper',x:1.02,yref:'y',y:all.length-2-index,
    text:group.band_ratio==null?'—':`${(group.band_ratio*100).toFixed(1)}% (${group.band_hits}/${group.n})`,showarrow:false,xanchor:'left',font:{size:11,color:'#333'}}))
  const line=(x:number,dash:'solid'|'dash'='solid'):Partial<Shape>=>({type:'line',xref:'x',yref:'paper',x0:x,x1:x,y0:0,y1:1,line:{color:'#222',width:1,dash}})
  const rawTraces=(difference=false,referenceBand=false):Data[] => (difference?tests:all).map((group,index)=>({
    type:'scatter',mode:'markers',name:group.line,
    x:group.points.map(point=>difference?(ref.mean == null?null:point.value-ref.mean):point.value),
    y:group.points.map((point,i)=>(difference?index:all.length-1-index)+similarityJitter(`${group.line}:${point.source_result_id}:${i}`,referenceBand&&index===0?0.04:0.06)),
    customdata:group.points.map(point=>[point.batch_number??'未提供',point.source_result_id??'未提供',group.line]),
    marker:{color:(difference?compareColors:allColors)[index],size:8,opacity:referenceBand&&index===0?0.85:0.9,line:{color:'#000',width:0.5}},
    hovertemplate:'%{customdata[2]}<br>数值 %{x}<br>批号 %{customdata[0]}<br>来源编号 %{customdata[1]}<extra></extra>',
  }))
  const chart=(title:string,data:Data[],layout:Partial<Layout>={},note?:string,rows=tests.length)=>
    <SimilarityPlot title={title} data={data} layout={layout} note={note} rows={rows} filename={panel.scope.attribute_name+'_'+title} />
  return <>
    {panel.warnings.map(warning=><Alert key={warning} type="warning" showIcon message={warning} style={{marginBottom:8}} />)}
    <div className="qap-similarity-grid">
      {chart('图0 · 参考均值', [{type:'bar',x:[ref.line],y:[ref.mean],marker:{color:'skyblue',line:{color:'#222',width:0.8}},
        error_y:{type:'data',array:[ref.sd??0],visible:ref.sd!=null},text:[`Mean=${fmt(ref.mean)}<br>SD=${fmt(ref.sd)} · N=${ref.n}`],textposition:'outside',cliponaxis:false}],
        {margin:{l:60,r:20,t:60,b:60},yaxis:{title:{text:panel.scope.unit||'存储原值'},rangemode:'tozero',tickfont:{weight:'normal'}}},'误差线为样本SD；本阶段不显示置信区间。',1)}
      {chart('图1 · 均值差比较',tests.map((group,index)=>({type:'bar',orientation:'h',y:[index],x:[group.mean_difference],
        marker:{color:compareColors[index],line:{color:'#222',width:0.8}},width:0.45,text:[fmt(group.mean_difference)],textposition:'auto'})),
        {shapes:[line(0)],yaxis:compareAxis,xaxis:{title:{text:'比较组均值 − 参比组均值'},range:symmetricLimits(tests.map(group=>group.mean_difference??NaN))}},'仅描述均值差；未进行TOST或等效判定。')}
      {chart('图2 · 个体差值散点',rawTraces(true),{shapes:[line(0)],yaxis:compareAxis,xaxis:{title:{text:'每条观察 − 参比均值'},range:symmetricLimits(differences)}})}
      {chart('图3 · 差值范围条',tests.map((group,index)=>({type:'bar',orientation:'h',
        base:[ref.mean!=null&&group.min!=null?group.min-ref.mean:0],x:[group.min!=null&&group.max!=null&&ref.mean!=null?group.max-group.min:null],y:[index],width:0.45,
        marker:{color:compareColors[index],line:{color:'#000',width:0.8}},name:group.line,hoverinfo:'skip'})),
        {shapes:[line(0)],annotations:rangeAnnotations,yaxis:compareAxis,xaxis:{title:{text:'最小 / 最大观察 − 参比均值'},range:symmetricLimits(differences)}},'范围条不是置信区间。')}
      {chart('图4 · 原始分布',rawTraces(),
        {yaxis:rawAxis,xaxis:{title:{text:panel.scope.unit||'存储原值'},range:expandLimits(allValues,0.33)}},'纵向错开重叠点，横坐标保留原始值。',all.length)}
      {chart('图5 · 参考SD带（探索）',rawTraces(false,true),{shapes:[...(ref.mean!=null?[line(ref.mean)]:[]),
        ...(band.lower!=null&&band.upper!=null?[{type:'rect' as const,xref:'x' as const,yref:'paper' as const,x0:band.lower,x1:band.upper,y0:0,y1:1,fillcolor:'rgba(31,119,180,0.08)',line:{width:0},layer:'below' as const},line(band.lower,'dash'),line(band.upper,'dash')]:[])],
        annotations:bandAnnotations,margin:{l:75,r:100,t:35,b:60},yaxis:{...rawAxis,range:[-0.4,all.length-0.6],ticktext:all.map((group,index)=>group.line+(index===0?' (Ref)':''))},
        xaxis:{title:{text:panel.scope.unit||'存储原值'},range:ref.mean!=null?[ref.mean-bandRadius,ref.mean+bandRadius]:expandLimits(allValues)}},`参比均值 ± ${band.k}×样本SD：[${fmt(band.lower)}, ${fmt(band.upper)}]；右侧比例仅描述落入情况，不作判定。`,all.length)}
    </div>
    <h3 className="qap-section-heading">统计汇总</h3>
    <Table size="small" rowKey="line" pagination={false} scroll={{x:950}} dataSource={[{...ref,role:'参比',mean_difference:null,band_ratio:null},...tests.map(group=>({...group,role:'比较'}))]}
      columns={[{title:'产线',dataIndex:'line',fixed:'left',width:110},{title:'用途',dataIndex:'role'},{title:'观察数 N',dataIndex:'n'},
        {title:'Mean',dataIndex:'mean',render:fmt},{title:'SD',dataIndex:'sd',render:fmt},{title:'最小值',dataIndex:'min',render:fmt},{title:'最大值',dataIndex:'max',render:fmt},
        {title:'均值差',dataIndex:'mean_difference',render:fmt},{title:'参考带内比例',dataIndex:'band_ratio',render:value=>value==null?'—':(value*100).toFixed(1)+'%'},
        {title:'排除非有限值',dataIndex:'excluded_n'}]} />
    <Collapse className="qap-summary" items={[{key:'rows',label:'查看原始观察与来源编号',children:<Table size="small" pagination={{pageSize:20,showSizeChanger:false}} scroll={{x:700}} rowKey="key"
      dataSource={all.flatMap(group=>group.points.map((point,index)=>({...point,line:group.line,key:group.line+':'+index})))}
      columns={[{title:'产线',dataIndex:'line'},{title:'组别',dataIndex:'group_id'},{title:'批号',dataIndex:'batch_number'},{title:'原值',dataIndex:'value',render:fmt},{title:'来源结果编号',dataIndex:'source_result_id'}]} />}]} />
  </>
}
