import { useState } from 'react';
import type { LLMConfigCreate } from '../types/llm';

interface LLMConfigFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (config: LLMConfigCreate) => Promise<void>;
}

export default function LLMConfigForm({
  isOpen,
  onClose,
  onSubmit,
}: LLMConfigFormProps) {
  const [formData, setFormData] = useState<LLMConfigCreate>({
    name: '',
    description: '',
    base_url: '',
    api_key: '',
    model_name: '',
    is_active: false,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await onSubmit(formData);
      // Reset form and close
      setFormData({
        name: '',
        description: '',
        base_url: '',
        api_key: '',
        model_name: '',
        is_active: false,
      });
      onClose();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create configuration'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (
    field: keyof LLMConfigCreate,
    value: string | boolean
  ) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-100">
            Add New LLM Configuration
          </h2>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-160px)]"
        >
          {error && (
            <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-2">
              Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={e => handleChange('name', e.target.value)}
              placeholder="e.g., OpenRouter - GPT-4"
              required
              maxLength={100}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-2">
              Description
            </label>
            <input
              type="text"
              value={formData.description}
              onChange={e => handleChange('description', e.target.value)}
              placeholder="e.g., OpenAI GPT-4 via OpenRouter"
              maxLength={500}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Base URL */}
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-2">
              Base URL <span className="text-red-400">*</span>
            </label>
            <input
              type="url"
              value={formData.base_url}
              onChange={e => handleChange('base_url', e.target.value)}
              placeholder="e.g., https://api.openai.com/v1"
              required
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="text-xs text-slate-400 mt-1">
              The API endpoint URL (e.g., OpenRouter, OpenAI, local LM Studio)
            </p>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-2">
              API Key <span className="text-red-400">*</span>
            </label>
            <input
              type="password"
              value={formData.api_key}
              onChange={e => handleChange('api_key', e.target.value)}
              placeholder="sk-..."
              required
              maxLength={500}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="text-xs text-slate-400 mt-1">
              Your authentication key (use "not-needed" for local instances)
            </p>
          </div>

          {/* Model Name */}
          <div>
            <label className="block text-sm font-medium text-slate-200 mb-2">
              Model Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={formData.model_name}
              onChange={e => handleChange('model_name', e.target.value)}
              placeholder="e.g., gpt-4 or qwen/qwen3-235b-a22b:free"
              required
              maxLength={200}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <p className="text-xs text-slate-400 mt-1">
              The model identifier (leave empty for local instances if needed)
            </p>
          </div>

          {/* Make Active */}
          <div className="flex items-center justify-between p-4 bg-slate-700/30 rounded-lg">
            <div>
              <label className="block text-sm font-medium text-slate-200">
                Activate Immediately
              </label>
              <p className="text-xs text-slate-400">
                Make this the active LLM configuration
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleChange('is_active', !formData.is_active)}
              className={`
                relative w-12 h-6 rounded-full transition-colors
                ${formData.is_active ? 'bg-purple-600' : 'bg-slate-600'}
              `}
            >
              <div
                className={`
                  absolute top-1 w-4 h-4 bg-white rounded-full transition-transform
                  ${formData.is_active ? 'translate-x-7' : 'translate-x-1'}
                `}
              />
            </button>
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-slate-300 hover:text-slate-100 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Creating...' : 'Create Configuration'}
          </button>
        </div>
      </div>
    </div>
  );
}
