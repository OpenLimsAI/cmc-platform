export type State='success'|'failed'|'warning'|'unknown'|'disabled'
export type Kind='etl'|'backup'|'monitor'|'sync'
export interface Task {key:string;name:string;kind:Kind;project:string;scope:string;enabled:boolean|null;times:string[];timeout_minutes:number;notes:string[];archive_device?:'vicell'|'flex2'|null;unit?:string}
export interface Evidence {id:string;kind:string;ref:string;excerpt:string}
export interface Run {archive_mode?:'day'|'night'|null;parent_run_id?:string|null;id:string;task_key:string;start:string;finish:string|null;status:string;message:string;duration_seconds:number|null;rows:number|null;files:number|null;size_bytes:number|null;children:{name:string;status:string;source_run_id?:number}[];evidence:Evidence[];integrity:string|null;restore:string|null;verification?:{status:string;reason?:string;started_at?:string|null;finished_at?:string|null;target_pg_version?:string;failure_step?:string|null;cleanup_status?:string;artifact?:string;sha256?:string;checks?:Record<string,string>};source_kind:string}
export interface Observation {task:Task;observed_at:string;collection_status:string;state:State;label:string;reasons:string[];last_run:Run|null;next_at:string|null;gaps:string[]}
export interface Snapshot {id:string;collected_at:string;trigger:string;tasks:Observation[];mode:string;gaps:string[];inventory_version:string;rule_version:string}
export interface History {snapshot_id:string;items:Run[];total:number;has_more:boolean;cutoff:string}
