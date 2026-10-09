export const pageTitles = {overview:'总览', trends:'取样点趋势'} as const
export type Section = keyof typeof pageTitles

export function readPage(pathname:string):{section:Section, removed:boolean} {
  const name=pathname.split('/')[2]
  return {section:name==='trends'?'trends':'overview', removed:['results','summaries','quality'].includes(name)}
}

export function pageURL(section:Section, search='') {
  return `/water/${section}${section==='trends'&&search?'?'+search:''}`
}
