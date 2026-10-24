import { useEffect, useRef, useState } from 'react'
import Plot from 'react-plotly.js'
import type { Data, Layout } from 'plotly.js'

export default function SimilarityPlot({title,data,layout={},note,filename,rows=1}: {
  title:string; data:Data[]; layout?:Partial<Layout>; note?:string; filename:string; rows?:number
}) {
  const container=useRef<HTMLDivElement>(null)
  const [width,setWidth]=useState(440)
  useEffect(()=>{
    if(!container.current)return
    const observer=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width))
    observer.observe(container.current)
    return ()=>observer.disconnect()
  },[])
  // Old figure is 8.5 x (5 + .3 per row after six) inches. Keep a readable minimum.
  const height=Math.max(260,Math.round(width*(5+Math.max(0,rows-6)*0.3)/8.5))
  return <div className="qap-similarity-chart" ref={container}>
    <h3>{title}</h3>
    <Plot data={data} layout={{autosize:true,showlegend:false,paper_bgcolor:'#fff',plot_bgcolor:'#fff',
      font:{family:'PingFang SC, Microsoft YaHei, Arial, sans-serif',size:12,color:'#1B2631'},margin:{l:75,r:20,t:35,b:60},...layout,
      xaxis:{gridcolor:'rgba(0,0,0,0.22)',griddash:'dot',gridwidth:0.8,showline:true,linecolor:'#222',zeroline:false,automargin:true,
        minor:{showgrid:true,gridcolor:'rgba(0,0,0,0.10)',griddash:'dot'},...layout.xaxis},
      yaxis:{automargin:true,showgrid:false,showline:true,linecolor:'#222',zeroline:false,tickfont:{size:12,weight:'bold'},...layout.yaxis},height}}
      config={{displaylogo:false,responsive:true,toImageButtonOptions:{format:'png',filename},modeBarButtonsToRemove:['lasso2d','select2d']}}
      useResizeHandler style={{width:'100%',height}} />
    {note&&<p className="qap-hint">{note}</p>}
  </div>
}
