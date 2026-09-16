// Display rules ported from the old analytics/similarity_plot.py.
const fixed = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
const tab20 = ['#1f77b4','#aec7e8','#ff7f0e','#ffbb78','#2ca02c','#98df8a','#d62728','#ff9896','#9467bd','#c5b0d5',
  '#8c564b','#c49c94','#e377c2','#f7b6d2','#7f7f7f','#c7c7c7','#bcbd22','#dbdb8d','#17becf','#9edae5']
export const similarityColors = (count: number) => Array.from({length:count}, (_,i) => i < fixed.length ? fixed[i]
  : tab20[Math.min(19, Math.floor(20 * 0.95 * (i - fixed.length) / (count - fixed.length)))])

export function expandLimits(values: number[], padding = 0.15): [number,number] {
  const finite = values.filter(Number.isFinite)
  if (!finite.length) return [-1,1]
  const low = finite.reduce((a,b)=>Math.min(a,b)), high = finite.reduce((a,b)=>Math.max(a,b))
  const pad = high > low ? (high-low)*padding : Math.max(Math.abs(low),Math.abs(high),1)*padding
  return [low-pad, high+pad]
}

export function symmetricLimits(values: number[]): [number,number] {
  const finite = values.filter(Number.isFinite)
  const radius = (finite.length ? finite.reduce((max,value)=>Math.max(max,Math.abs(value)),1e-9) : 1) / 0.85
  return [-radius,radius]
}

// Stable per observation, so resizing or re-rendering cannot move the points.
// Unlike the old shared RNG, this does not depend on previous chart calls.
export function similarityJitter(key: string, amplitude = 0.06): number {
  let hash = 2166136261
  for (const char of key) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619)
  return ((hash >>> 0) / 4294967295 - 0.5) * 2 * amplitude
}
