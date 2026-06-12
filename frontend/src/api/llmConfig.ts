/**
 * LLM Configuration API Client
 *
 * Functions for interacting with the LLM configuration endpoints
 */

import axios from 'axios';
import type {
  LLMConfiguration,
  LLMConfigCreate,
  LLMConfigUpdate,
  LLMConfigListResponse,
  LLMActivateResponse,
  LLMTestResponse,
} from '../types/llm';
import { api } from '../services/http';

/** Backend `detail` message from an axios error, when present. */
function errorDetail(error: unknown): string | undefined {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return undefined;
}

/**
 * List all LLM configurations
 */
export async function listLLMConfigurations(): Promise<LLMConfiguration[]> {
  try {
    const response = await api.get<LLMConfigListResponse>('/llm-config/list');
    return response.data.configurations;
  } catch {
    throw new Error('Failed to fetch LLM configurations');
  }
}

/**
 * Get the active LLM configuration
 */
export async function getActiveLLMConfiguration(): Promise<LLMConfiguration> {
  try {
    const response = await api.get<LLMConfiguration>('/llm-config/active');
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      throw new Error('No active LLM configuration found');
    }
    throw new Error('Failed to fetch active LLM configuration');
  }
}

/**
 * Get a specific LLM configuration by ID
 */
export async function getLLMConfiguration(
  id: number
): Promise<LLMConfiguration> {
  try {
    const response = await api.get<LLMConfiguration>(`/llm-config/${id}`);
    return response.data;
  } catch {
    throw new Error(`Failed to fetch LLM configuration ${id}`);
  }
}

/**
 * Create a new LLM configuration
 */
export async function createLLMConfiguration(
  config: LLMConfigCreate
): Promise<LLMConfiguration> {
  try {
    const response = await api.post<LLMConfiguration>('/llm-config', config);
    return response.data;
  } catch (error) {
    throw new Error(errorDetail(error) || 'Failed to create LLM configuration');
  }
}

/**
 * Update an existing LLM configuration
 */
export async function updateLLMConfiguration(
  id: number,
  updates: LLMConfigUpdate
): Promise<LLMConfiguration> {
  try {
    const response = await api.put<LLMConfiguration>(
      `/llm-config/${id}`,
      updates
    );
    return response.data;
  } catch (error) {
    throw new Error(errorDetail(error) || 'Failed to update LLM configuration');
  }
}

/**
 * Activate an LLM configuration (deactivates others)
 */
export async function activateLLMConfiguration(
  id: number
): Promise<LLMActivateResponse> {
  try {
    const response = await api.put<LLMActivateResponse>(
      `/llm-config/${id}/activate`
    );
    return response.data;
  } catch (error) {
    throw new Error(
      errorDetail(error) || 'Failed to activate LLM configuration'
    );
  }
}

/**
 * Delete an LLM configuration (cannot delete active)
 */
export async function deleteLLMConfiguration(id: number): Promise<void> {
  try {
    await api.delete(`/llm-config/${id}`);
  } catch (error) {
    throw new Error(errorDetail(error) || 'Failed to delete LLM configuration');
  }
}

/**
 * Test connection to an LLM configuration
 */
export async function testLLMConnection(id: number): Promise<LLMTestResponse> {
  try {
    const response = await api.post<LLMTestResponse>(`/llm-config/${id}/test`);
    return response.data;
  } catch {
    throw new Error('Failed to test LLM connection');
  }
}
