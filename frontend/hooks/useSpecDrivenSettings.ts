/**
 * @module useSpecDrivenSettings
 * @description React Query hooks for Spec-Driven Settings management
 *
 * Manages settings for the spec-driven development workflow, including:
 * - Auto-execution mode (auto/manual)
 * - Coverage requirements
 * - Parallel execution toggles
 * - Validation mode (strict/relaxed)
 *
 * @example
 * ```tsx
 * function SettingsPanel() {
 *   const { data: settings } = useSpecDrivenSettings();
 *   const update = useUpdateSpecDrivenSettings();
 *   const reset = useResetSpecDrivenSettings();
 *
 *   return (
 *     <div>
 *       <label>
 *         Auto-execute:
 *         <input
 *           type="checkbox"
 *           checked={settings?.auto_execute}
 *           onChange={(e) => update.mutate({ auto_execute: e.target.checked })}
 *         />
 *       </label>
 *       <button onClick={() => reset.mutate()}>Reset to Defaults</button>
 *     </div>
 *   );
 * }
 * ```
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

// Types for spec-driven settings
export interface SpecDrivenSettings {
  id: string;
  user_id: string;
  // Execution mode
  auto_execute: boolean;
  execution_mode: "auto" | "manual";
  // Coverage settings
  coverage_threshold: number; // 0-100
  enforce_coverage: boolean;
  // Parallel execution
  parallel_execution: boolean;
  max_parallel_tasks: number;
  // Validation
  validation_mode: "strict" | "relaxed" | "none";
  require_tests: boolean;
  require_docs: boolean;
  // Advanced
  auto_merge: boolean;
  notify_on_completion: boolean;
  created_at: string;
  updated_at: string;
}

export interface SpecDrivenSettingsUpdate {
  auto_execute?: boolean;
  execution_mode?: "auto" | "manual";
  coverage_threshold?: number;
  enforce_coverage?: boolean;
  parallel_execution?: boolean;
  max_parallel_tasks?: number;
  validation_mode?: "strict" | "relaxed" | "none";
  require_tests?: boolean;
  require_docs?: boolean;
  auto_merge?: boolean;
  notify_on_completion?: boolean;
}

// Default settings
export const DEFAULT_SETTINGS: Omit<
  SpecDrivenSettings,
  "id" | "user_id" | "created_at" | "updated_at"
> = {
  auto_execute: true,
  execution_mode: "auto",
  coverage_threshold: 80,
  enforce_coverage: true,
  parallel_execution: true,
  max_parallel_tasks: 3,
  validation_mode: "strict",
  require_tests: true,
  require_docs: false,
  auto_merge: false,
  notify_on_completion: true,
};

// Risky configuration checks
export interface SettingsWarning {
  field: string;
  message: string;
  severity: "warning" | "error";
}

/**
 * Get warnings for potentially risky settings configurations
 * @param settings - Partial settings to check
 * @returns Array of warnings with field, message, and severity
 * @example
 * ```tsx
 * const warnings = getSettingsWarnings({ auto_merge: true, validation_mode: "none" });
 * // warnings = [{ field: "auto_merge", message: "...", severity: "warning" }]
 * ```
 */
export function getSettingsWarnings(
  settings: Partial<SpecDrivenSettings>,
): SettingsWarning[] {
  const warnings: SettingsWarning[] = [];

  if (settings.auto_merge && settings.validation_mode === "none") {
    warnings.push({
      field: "auto_merge",
      message:
        "Auto-merge with no validation is risky. Consider enabling validation.",
      severity: "warning",
    });
  }

  if (
    settings.coverage_threshold !== undefined &&
    settings.coverage_threshold < 50 &&
    settings.enforce_coverage
  ) {
    warnings.push({
      field: "coverage_threshold",
      message: "Coverage threshold below 50% may result in low-quality code.",
      severity: "warning",
    });
  }

  if (
    settings.parallel_execution &&
    settings.max_parallel_tasks !== undefined &&
    settings.max_parallel_tasks > 5
  ) {
    warnings.push({
      field: "max_parallel_tasks",
      message: "Running more than 5 parallel tasks may impact performance.",
      severity: "warning",
    });
  }

  if (!settings.require_tests && settings.auto_merge) {
    warnings.push({
      field: "require_tests",
      message: "Auto-merge without required tests could introduce bugs.",
      severity: "error",
    });
  }

  return warnings;
}

// Validation
export interface ValidationError {
  field: string;
  message: string;
}

/**
 * Validate settings values
 * @param settings - Partial settings to validate
 * @returns Array of validation errors with field and message
 * @example
 * ```tsx
 * const errors = validateSettings({ coverage_threshold: 150 });
 * // errors = [{ field: "coverage_threshold", message: "Coverage must be between 0 and 100" }]
 * ```
 */
export function validateSettings(
  settings: Partial<SpecDrivenSettings>,
): ValidationError[] {
  const errors: ValidationError[] = [];

  if (settings.coverage_threshold !== undefined) {
    if (settings.coverage_threshold < 0 || settings.coverage_threshold > 100) {
      errors.push({
        field: "coverage_threshold",
        message: "Coverage must be between 0 and 100",
      });
    }
  }

  if (settings.max_parallel_tasks !== undefined) {
    if (settings.max_parallel_tasks < 1 || settings.max_parallel_tasks > 10) {
      errors.push({
        field: "max_parallel_tasks",
        message: "Parallel tasks must be between 1 and 10",
      });
    }
  }

  return errors;
}

// Query keys
export const specDrivenSettingsKeys = {
  all: ["spec-driven-settings"] as const,
  detail: () => [...specDrivenSettingsKeys.all, "detail"] as const,
};

// API functions
async function fetchSpecDrivenSettings(): Promise<SpecDrivenSettings> {
  const response = await api.get<SpecDrivenSettings>(
    "/api/v1/settings/spec-driven",
  );
  return response;
}

async function updateSpecDrivenSettings(
  data: SpecDrivenSettingsUpdate,
): Promise<SpecDrivenSettings> {
  const response = await api.patch<SpecDrivenSettings>(
    "/api/v1/settings/spec-driven",
    data,
  );
  return response;
}

async function resetSpecDrivenSettings(): Promise<SpecDrivenSettings> {
  const response = await api.post<SpecDrivenSettings>(
    "/api/v1/settings/spec-driven/reset",
    {},
  );
  return response;
}

/**
 * Hook to fetch spec-driven settings
 * @returns Query result with SpecDrivenSettings data
 * @example
 * ```tsx
 * const { data: settings, isLoading, error } = useSpecDrivenSettings();
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 * return <SettingsForm settings={settings} />;
 * ```
 */
export function useSpecDrivenSettings() {
  return useQuery({
    queryKey: specDrivenSettingsKeys.detail(),
    queryFn: fetchSpecDrivenSettings,
  });
}

/**
 * Hook to update spec-driven settings
 * @returns Mutation result for updating settings
 * @example
 * ```tsx
 * const update = useUpdateSpecDrivenSettings();
 * const handleToggle = (checked: boolean) => {
 *   update.mutate({ auto_execute: checked });
 * };
 * ```
 */
export function useUpdateSpecDrivenSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SpecDrivenSettingsUpdate) =>
      updateSpecDrivenSettings(data),
    onSuccess: (data) => {
      queryClient.setQueryData(specDrivenSettingsKeys.detail(), data);
    },
  });
}

/**
 * Hook to reset spec-driven settings to defaults
 * @returns Mutation result for resetting settings
 * @example
 * ```tsx
 * const reset = useResetSpecDrivenSettings();
 * return <button onClick={() => reset.mutate()}>Reset to Defaults</button>;
 * ```
 */
export function useResetSpecDrivenSettings() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => resetSpecDrivenSettings(),
    onSuccess: (data) => {
      queryClient.setQueryData(specDrivenSettingsKeys.detail(), data);
    },
  });
}
