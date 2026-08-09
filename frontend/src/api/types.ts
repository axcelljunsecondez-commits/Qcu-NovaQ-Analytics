export type Role = 'admin' | 'analyst'

export interface UserOut {
  id: number
  email: string
  role: Role
  active: boolean
  created_at: string
}

export interface LoginResponse {
  user: UserOut
}

export interface MeResponse {
  user: UserOut | null
}

export interface SegmentInput {
  time: string
  lambda: number
  mu: number
  c: number
  variance?: number
  K?: number
  theta?: number
}

export interface OptimizationOut {
  time: string
  lambda_: number
  mu: number
  c_current: number
  c_optimal: number
  rho_current: number | null
  rho_optimal: number | null
  Wq_current: number | null
  Wq_optimal: number | null
  Lq_current: number | null
  Lq_optimal: number | null
  cost_current: number | null
  cost_optimal: number | null
  delta_cost: number | null
  delta_Wq: number | null
  delta_Lq: number | null
  delta_c: number
  delta_rho: number | null
  waiting_cost_current: number | null
  waiting_cost_optimal: number | null
  abandonment_cost_current: number | null
  abandonment_cost_optimal: number | null
  cost_per_server: number | null
  current_stable: boolean
  optimized_stable: boolean
  recommendation: string
  warning: string
}

export interface AnalysisOut {
  rho: number
  L: number | null
  Lq: number | null
  W: number | null
  Wq: number | null
  stable: boolean
  error: string | null
  blocking_probability?: number
  effective_lambda?: number
  K?: number
  approximation?: string
  rho_effective?: number
  theta?: number
  lambda_eff?: number
  abandonment_rate?: number
}

export interface DatasetValidation {
  ok: boolean
  message: string
}

export interface DatasetOut {
  id: number
  name: string
  source_filename: string
  source_format: string
  row_count: number
  validation: DatasetValidation
  created_at: string
  normalized: Record<string, unknown>[] | null
}

export interface ScenarioOut {
  id: number
  user_id: number
  dataset_id: number | null
  name: string
  settings: Record<string, unknown>
  results: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AdminUserOut {
  id: number
  email: string
  role: Role
  active: boolean
  created_at: string
}

export interface CreateUserRequest {
  email: string
  password: string
  role: Role
}

export interface UpdateUserRequest {
  role?: Role
  active?: boolean
}
