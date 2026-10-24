export const filterFields = [
  ['water_type','水类型','samplesubtypeid'],
  ['samplepoint_code','水点号','samplepoint_code'],
  ['samplepoint_id','水点（编号 / 名称 / 内部 ID）','samplepointid'],
  ['workitem_id','检项','workitemid'],
  ['paramlist_id','方法','paramlistid'],
  ['paramlist_version_id','版本','paramlistversionid'],
  ['variant_id','阶段','variantid'],
  ['param_id','参数','paramid'],
  ['unit','单位','unit'],
] as const

// Date/status changes keep the water type and reset all point/method selections.
export function changeFilters(current:Record<string,any>, changes:Record<string,any>) {
  const next={...current,...changes}
  let resetFrom:number=filterFields.length
  for (const key of Object.keys(changes)) {
    if (key==='date_from'||key==='date_to'||key==='sample_status') resetFrom=Math.min(resetFrom,1)
    else {
      const index=filterFields.findIndex(([field])=>field===key)
      if(index>=0) resetFrom=Math.min(resetFrom,index+1)
    }
  }
  for(const [field] of filterFields.slice(resetFrom)) delete next[field]
  return next
}

export function choices(data:any,key:string,column:string) {
  if(key==='samplepoint_id') return data?.point_options||[]
  return (data?.options[column]||[]).filter((v:any)=>v!==null).map((v:any)=>({label:v,value:v}))
}
