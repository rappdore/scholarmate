import { useState, useEffect } from 'react';
import { HighlightColor } from '../types/highlights';
import { useSettings } from '../contexts/SettingsContext';
import type { LLMConfiguration, LLMConfigCreate } from '../types/llm';
import {
  listLLMConfigurations,
  activateLLMConfiguration,
  createLLMConfiguration,
  updateLLMConfiguration,
  deleteLLMConfiguration,
} from '../api/llmConfig';
import LLMConfigForm from './LLMConfigForm';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { settings, updateSettings, resetToDefaults } = useSettings();
  const [activeTab, setActiveTab] = useState<
    'viewer' | 'ui' | 'reading' | 'ai'
  >('viewer');

  // LLM configuration state
  const [llmConfigs, setLlmConfigs] = useState<LLMConfiguration[]>([]);
  const [isLoadingLlms, setIsLoadingLlms] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<LLMConfiguration | null>(
    null
  );
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  const tabs = [
    { id: 'viewer', label: 'PDF Viewer', icon: '📖' },
    { id: 'ui', label: 'Interface', icon: '🎨' },
    { id: 'reading', label: 'Reading', icon: '📚' },
    { id: 'ai', label: 'AI Assistant', icon: '🤖' },
  ] as const;

  // Fetch LLM configurations when AI tab is opened
  useEffect(() => {
    if (activeTab === 'ai' && isOpen) {
      fetchLLMConfigurations();
    }
  }, [activeTab, isOpen]);

  const fetchLLMConfigurations = async () => {
    setIsLoadingLlms(true);
    setLlmError(null);
    try {
      const configs = await listLLMConfigurations();
      setLlmConfigs(configs);
    } catch (error) {
      console.error('Failed to fetch LLM configurations:', error);
      setLlmError(
        error instanceof Error
          ? error.message
          : 'Failed to load LLM configurations'
      );
    } finally {
      setIsLoadingLlms(false);
    }
  };

  const handleActivateLLM = async (configId: number) => {
    try {
      await activateLLMConfiguration(configId);
      // Refresh configurations to get updated active status
      await fetchLLMConfigurations();
      // Notify other components that LLM config changed
      window.dispatchEvent(new CustomEvent('llm-config-changed'));
    } catch (error) {
      console.error('Failed to activate LLM:', error);
      setLlmError(
        error instanceof Error ? error.message : 'Failed to activate LLM'
      );
    }
  };

  const handleCreateLLM = async (config: LLMConfigCreate) => {
    try {
      await createLLMConfiguration(config);
      // Refresh configurations to show the new one
      await fetchLLMConfigurations();
      // If the new config was set as active, notify other components
      if (config.is_active) {
        window.dispatchEvent(new CustomEvent('llm-config-changed'));
      }
    } catch (error) {
      console.error('Failed to create LLM configuration:', error);
      throw error; // Re-throw to let form handle the error
    }
  };

  const handleUpdateLLM = async (config: LLMConfigCreate) => {
    if (!editingConfig) return;

    try {
      // Only send fields that have values (for partial update)
      const updates: any = {
        name: config.name,
        description: config.description,
        base_url: config.base_url,
        model_name: config.model_name,
        always_starts_with_thinking: config.always_starts_with_thinking,
      };

      // Only include API key if it was changed (not empty)
      if (config.api_key) {
        updates.api_key = config.api_key;
      }

      await updateLLMConfiguration(editingConfig.id, updates);
      // Refresh configurations to show the updated one
      await fetchLLMConfigurations();
      setEditingConfig(null);
    } catch (error) {
      console.error('Failed to update LLM configuration:', error);
      throw error; // Re-throw to let form handle the error
    }
  };

  const handleFormSubmit = async (config: LLMConfigCreate) => {
    if (editingConfig) {
      await handleUpdateLLM(config);
    } else {
      await handleCreateLLM(config);
    }
  };

  const handleFormClose = () => {
    setIsFormOpen(false);
    setEditingConfig(null);
  };

  const handleEditClick = (config: LLMConfiguration) => {
    setEditingConfig(config);
    setIsFormOpen(true);
  };

  const handleDeleteLLM = async (configId: number) => {
    try {
      await deleteLLMConfiguration(configId);
      // Refresh configurations to remove the deleted one
      await fetchLLMConfigurations();
      setDeleteConfirmId(null);
    } catch (error) {
      console.error('Failed to delete LLM configuration:', error);
      setLlmError(
        error instanceof Error
          ? error.message
          : 'Failed to delete LLM configuration'
      );
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-4xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-100">Settings</h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg transition-colors"
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

        <div className="flex">
          {/* Sidebar */}
          <div className="w-48 bg-slate-900/50 border-r border-slate-700">
            <div className="p-4 space-y-1">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center space-x-3
                    ${
                      activeTab === tab.id
                        ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30'
                        : 'text-slate-300 hover:bg-slate-700/50 hover:text-slate-200'
                    }
                  `}
                >
                  <span>{tab.icon}</span>
                  <span className="font-medium">{tab.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Content */}
          <div className="flex-1 p-6 overflow-y-auto max-h-[calc(90vh-80px)]">
            {activeTab === 'viewer' && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-slate-100 mb-4">
                  PDF Viewer Settings
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-200 mb-2">
                      Default Zoom Level
                    </label>
                    <div className="flex items-center space-x-4">
                      <input
                        type="range"
                        min="0.5"
                        max="3.0"
                        step="0.1"
                        value={settings.defaultZoom}
                        onChange={e =>
                          updateSettings({
                            defaultZoom: parseFloat(e.target.value),
                          })
                        }
                        className="flex-1"
                      />
                      <span className="text-slate-300 w-16">
                        {Math.round(settings.defaultZoom * 100)}%
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-200 mb-2">
                      Default View Mode
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {(['single', 'double'] as const).map(mode => (
                        <button
                          key={mode}
                          onClick={() =>
                            updateSettings({ defaultViewMode: mode })
                          }
                          className={`
                            p-3 rounded-lg border text-center transition-colors
                            ${
                              settings.defaultViewMode === mode
                                ? 'bg-purple-600/20 border-purple-500/50 text-purple-300'
                                : 'bg-slate-700/30 border-slate-600 text-slate-300 hover:bg-slate-700/50'
                            }
                          `}
                        >
                          {mode === 'single'
                            ? '📄 Single Page'
                            : '📑 Double Page'}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-200 mb-2">
                      Default Highlight Color
                    </label>
                    <div className="grid grid-cols-4 gap-2">
                      {Object.values(HighlightColor).map(color => (
                        <button
                          key={color}
                          onClick={() =>
                            updateSettings({ defaultHighlightColor: color })
                          }
                          className={`
                            w-12 h-12 rounded-lg border-2 transition-all
                            ${
                              settings.defaultHighlightColor === color
                                ? 'border-white scale-110'
                                : 'border-slate-600 hover:border-slate-400'
                            }
                          `}
                          style={{ backgroundColor: color }}
                          title={color}
                        />
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-200 mb-2">
                      Highlight Opacity
                    </label>
                    <div className="flex items-center space-x-4">
                      <input
                        type="range"
                        min="0.1"
                        max="0.8"
                        step="0.1"
                        value={settings.highlightOpacity}
                        onChange={e =>
                          updateSettings({
                            highlightOpacity: parseFloat(e.target.value),
                          })
                        }
                        className="flex-1"
                      />
                      <span className="text-slate-300 w-16">
                        {Math.round(settings.highlightOpacity * 100)}%
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'ui' && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-slate-100 mb-4">
                  Interface Settings
                </h3>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-200 mb-2">
                      Default Panel Layout
                    </label>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">
                          Left Panel Width (%)
                        </label>
                        <input
                          type="number"
                          min="20"
                          max="80"
                          value={settings.defaultLeftPanelWidth}
                          onChange={e =>
                            updateSettings({
                              defaultLeftPanelWidth: parseInt(e.target.value),
                            })
                          }
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">
                          Right Top Panel Height (%)
                        </label>
                        <input
                          type="number"
                          min="20"
                          max="80"
                          value={settings.defaultRightTopPanelHeight}
                          onChange={e =>
                            updateSettings({
                              defaultRightTopPanelHeight: parseInt(
                                e.target.value
                              ),
                            })
                          }
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <label className="block text-sm font-medium text-slate-200">
                        Show Page Numbers
                      </label>
                      <p className="text-xs text-slate-400">
                        Display page numbers in PDF viewer
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        updateSettings({
                          showPageNumbers: !settings.showPageNumbers,
                        })
                      }
                      className={`
                        relative w-12 h-6 rounded-full transition-colors
                        ${settings.showPageNumbers ? 'bg-purple-600' : 'bg-slate-600'}
                      `}
                    >
                      <div
                        className={`
                        absolute top-1 w-4 h-4 bg-white rounded-full transition-transform
                        ${settings.showPageNumbers ? 'translate-x-7' : 'translate-x-1'}
                      `}
                      />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'reading' && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-slate-100 mb-4">
                  Reading Settings
                </h3>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="block text-sm font-medium text-slate-200">
                        Auto-save Reading Progress
                      </label>
                      <p className="text-xs text-slate-400">
                        Automatically save your reading position
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        updateSettings({
                          autoSaveProgress: !settings.autoSaveProgress,
                        })
                      }
                      className={`
                        relative w-12 h-6 rounded-full transition-colors
                        ${settings.autoSaveProgress ? 'bg-purple-600' : 'bg-slate-600'}
                      `}
                    >
                      <div
                        className={`
                        absolute top-1 w-4 h-4 bg-white rounded-full transition-transform
                        ${settings.autoSaveProgress ? 'translate-x-7' : 'translate-x-1'}
                      `}
                      />
                    </button>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <label className="block text-sm font-medium text-slate-200">
                        Auto-mark as Finished
                      </label>
                      <p className="text-xs text-slate-400">
                        Automatically mark books as finished when completed
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        updateSettings({
                          autoMarkFinished: !settings.autoMarkFinished,
                        })
                      }
                      className={`
                        relative w-12 h-6 rounded-full transition-colors
                        ${settings.autoMarkFinished ? 'bg-purple-600' : 'bg-slate-600'}
                      `}
                    >
                      <div
                        className={`
                        absolute top-1 w-4 h-4 bg-white rounded-full transition-transform
                        ${settings.autoMarkFinished ? 'translate-x-7' : 'translate-x-1'}
                      `}
                      />
                    </button>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-200 mb-2">
                      Daily Reading Goal (pages)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={settings.readingGoal}
                      onChange={e =>
                        updateSettings({
                          readingGoal: parseInt(e.target.value),
                        })
                      }
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-200"
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'ai' && (
              <div className="space-y-6">
                <h3 className="text-lg font-semibold text-slate-100 mb-4">
                  AI Assistant Settings
                </h3>

                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <label className="block text-sm font-medium text-slate-200">
                        Enable AI Assistant
                      </label>
                      <p className="text-xs text-slate-400">
                        Turn on/off AI-powered features
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        updateSettings({ enableAI: !settings.enableAI })
                      }
                      className={`
                        relative w-12 h-6 rounded-full transition-colors
                        ${settings.enableAI ? 'bg-purple-600' : 'bg-slate-600'}
                      `}
                    >
                      <div
                        className={`
                        absolute top-1 w-4 h-4 bg-white rounded-full transition-transform
                        ${settings.enableAI ? 'translate-x-7' : 'translate-x-1'}
                      `}
                      />
                    </button>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <label className="block text-sm font-medium text-slate-200">
                          LLM Configurations
                        </label>
                        <p className="text-xs text-slate-400 mt-1">
                          Manage and switch between LLM endpoints
                        </p>
                      </div>
                      <button
                        onClick={() => setIsFormOpen(true)}
                        className="px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white text-sm rounded-lg transition-colors flex items-center gap-1"
                      >
                        <svg
                          className="w-4 h-4"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 4v16m8-8H4"
                          />
                        </svg>
                        Add New
                      </button>
                    </div>

                    {isLoadingLlms ? (
                      <div className="flex items-center justify-center py-8">
                        <div className="text-slate-400">
                          Loading configurations...
                        </div>
                      </div>
                    ) : llmError ? (
                      <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
                        <p className="text-red-400 text-sm">{llmError}</p>
                        <button
                          onClick={fetchLLMConfigurations}
                          className="mt-2 text-xs text-red-300 hover:text-red-200 underline"
                        >
                          Retry
                        </button>
                      </div>
                    ) : llmConfigs.length === 0 ? (
                      <div className="p-4 bg-slate-700/30 border border-slate-600 rounded-lg">
                        <p className="text-slate-400 text-sm">
                          No LLM configurations found. Using default fallback
                          configuration.
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-96 overflow-y-auto">
                        {llmConfigs.map(config => (
                          <div
                            key={config.id}
                            className={`
                              relative group rounded-lg border transition-all
                              ${
                                config.is_active
                                  ? 'bg-purple-600/20 border-purple-500/50'
                                  : 'bg-slate-700/30 border-slate-600 hover:bg-slate-700/50 hover:border-slate-500'
                              }
                            `}
                          >
                            <button
                              onClick={() => handleActivateLLM(config.id)}
                              disabled={config.is_active}
                              className="w-full p-4 text-left"
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex-1 pr-2">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`font-medium ${
                                        config.is_active
                                          ? 'text-purple-300'
                                          : 'text-slate-300'
                                      }`}
                                    >
                                      {config.name}
                                    </span>
                                    {config.is_active && (
                                      <span className="text-xs px-2 py-0.5 bg-purple-500/30 text-purple-300 rounded">
                                        Active
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-xs text-slate-400 mt-1">
                                    {config.model_name}
                                  </div>
                                  {config.description && (
                                    <div className="text-xs text-slate-500 mt-1">
                                      {config.description}
                                    </div>
                                  )}
                                </div>
                                {!config.is_active && (
                                  <div className="flex items-center gap-1">
                                    <button
                                      onClick={e => {
                                        e.stopPropagation();
                                        handleEditClick(config);
                                      }}
                                      className="p-1.5 text-slate-400 hover:text-purple-400 hover:bg-purple-900/20 rounded transition-colors opacity-0 group-hover:opacity-100"
                                      title="Edit configuration"
                                    >
                                      <svg
                                        className="w-4 h-4"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                      >
                                        <path
                                          strokeLinecap="round"
                                          strokeLinejoin="round"
                                          strokeWidth={2}
                                          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                                        />
                                      </svg>
                                    </button>
                                    <button
                                      onClick={e => {
                                        e.stopPropagation();
                                        setDeleteConfirmId(config.id);
                                      }}
                                      className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-900/20 rounded transition-colors opacity-0 group-hover:opacity-100"
                                      title="Delete configuration"
                                    >
                                      <svg
                                        className="w-4 h-4"
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                      >
                                        <path
                                          strokeLinecap="round"
                                          strokeLinejoin="round"
                                          strokeWidth={2}
                                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                        />
                                      </svg>
                                    </button>
                                  </div>
                                )}
                              </div>
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-700 flex items-center justify-between">
          <button
            onClick={resetToDefaults}
            className="px-4 py-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg transition-colors"
          >
            Reset to Defaults
          </button>
          <div className="flex space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* LLM Configuration Form Modal */}
      <LLMConfigForm
        isOpen={isFormOpen}
        onClose={handleFormClose}
        onSubmit={handleFormSubmit}
        editingConfig={editingConfig}
      />

      {/* Delete Confirmation Dialog */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-slate-800 rounded-xl shadow-2xl border border-slate-700 w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-slate-100 mb-2">
              Delete LLM Configuration?
            </h3>
            <p className="text-sm text-slate-400 mb-6">
              Are you sure you want to delete this configuration? This action
              cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                className="px-4 py-2 text-slate-300 hover:text-slate-100 hover:bg-slate-700 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeleteLLM(deleteConfirmId)}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
