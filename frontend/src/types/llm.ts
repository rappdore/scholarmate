/**
 * LLM Configuration Types
 *
 * TypeScript types for LLM configuration management
 */

export interface LLMConfiguration {
  id: number;
  name: string;
  description?: string;
  base_url: string;
  model_name: string;
  is_active: boolean;
  always_starts_with_thinking: boolean;
  created_at: string;
  updated_at: string;
  api_key_preview: string;
}

export interface LLMConfigCreate {
  name: string;
  description?: string;
  base_url: string;
  api_key: string;
  model_name: string;
  is_active?: boolean;
  always_starts_with_thinking?: boolean;
}

export interface LLMConfigUpdate {
  name?: string;
  description?: string;
  base_url?: string;
  api_key?: string;
  model_name?: string;
  always_starts_with_thinking?: boolean;
}

export interface LLMConfigListResponse {
  configurations: LLMConfiguration[];
}

export interface LLMActivateResponse {
  message: string;
  previous_active_id: number | null;
  new_active_id: number;
  configuration: Partial<LLMConfiguration>;
}

export interface LLMTestResponse {
  success: boolean;
  message: string;
  model_name?: string;
  test_response?: string;
  latency_ms?: number;
  error?: string;
  error_type?: string;
}
