/**
 * LLM Configuration API Client
 *
 * Functions for interacting with the LLM configuration endpoints
 */

import type {
  LLMConfiguration,
  LLMConfigCreate,
  LLMConfigUpdate,
  LLMConfigListResponse,
  LLMActivateResponse,
  LLMTestResponse,
} from '../types/llm';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * List all LLM configurations
 */
export async function listLLMConfigurations(): Promise<LLMConfiguration[]> {
  const response = await fetch(`${API_BASE_URL}/llm-config/list`);
  if (!response.ok) {
    throw new Error('Failed to fetch LLM configurations');
  }
  const data: LLMConfigListResponse = await response.json();
  return data.configurations;
}

/**
 * Get the active LLM configuration
 */
export async function getActiveLLMConfiguration(): Promise<LLMConfiguration> {
  const response = await fetch(`${API_BASE_URL}/llm-config/active`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('No active LLM configuration found');
    }
    throw new Error('Failed to fetch active LLM configuration');
  }
  return response.json();
}

/**
 * Get a specific LLM configuration by ID
 */
export async function getLLMConfiguration(
  id: number
): Promise<LLMConfiguration> {
  const response = await fetch(`${API_BASE_URL}/llm-config/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch LLM configuration ${id}`);
  }
  return response.json();
}

/**
 * Create a new LLM configuration
 */
export async function createLLMConfiguration(
  config: LLMConfigCreate
): Promise<LLMConfiguration> {
  const response = await fetch(`${API_BASE_URL}/llm-config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to create LLM configuration');
  }

  return response.json();
}

/**
 * Update an existing LLM configuration
 */
export async function updateLLMConfiguration(
  id: number,
  updates: LLMConfigUpdate
): Promise<LLMConfiguration> {
  const response = await fetch(`${API_BASE_URL}/llm-config/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to update LLM configuration');
  }

  return response.json();
}

/**
 * Activate an LLM configuration (deactivates others)
 */
export async function activateLLMConfiguration(
  id: number
): Promise<LLMActivateResponse> {
  const response = await fetch(`${API_BASE_URL}/llm-config/${id}/activate`, {
    method: 'PUT',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to activate LLM configuration');
  }

  return response.json();
}

/**
 * Delete an LLM configuration (cannot delete active)
 */
export async function deleteLLMConfiguration(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/llm-config/${id}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to delete LLM configuration');
  }
}

/**
 * Test connection to an LLM configuration
 */
export async function testLLMConnection(id: number): Promise<LLMTestResponse> {
  const response = await fetch(`${API_BASE_URL}/llm-config/${id}/test`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error('Failed to test LLM connection');
  }

  return response.json();
}
