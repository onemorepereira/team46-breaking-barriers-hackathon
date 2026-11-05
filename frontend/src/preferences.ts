// Store display choices only: never prompts, reports, credentials or imagery.
export type Preferences = {
  reading: boolean;
  colour: "standard" | "colour-safe";
  contrast: boolean;
  largeText: boolean;
  reducedMotion: boolean;
};
export const defaults: Preferences = {
  reading: false,
  colour: "standard",
  contrast: false,
  largeText: false,
  reducedMotion: false,
};
export function readPreference<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(`foundry.ui.v2.${key}`);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}
export function writePreference(key: string, value: unknown): void {
  try {
    localStorage.setItem(`foundry.ui.v2.${key}`, JSON.stringify(value));
  } catch {
    /* Storage can be disabled; controls still work for this visit. */
  }
}
export function readAccessibility(): Preferences {
  const raw = readPreference<any>("accessibility", {});
  return {
    reading: raw?.reading === true,
    colour: raw?.colour === "colour-safe" ? "colour-safe" : "standard",
    contrast: raw?.contrast === true,
    largeText: raw?.largeText === true,
    reducedMotion: raw?.reducedMotion === true,
  };
}
export const PROMPT_TEMPLATE =
  "Find [asset type] in [area]. Return the exact locations, cite the tool evidence, and explain uncertainty.";
export function hasTemplateBlanks(prompt: string): boolean {
  return /\[(?:asset type|area)\]/i.test(prompt);
}
export function buildPrompt(asset: string, area: string): string {
  return `Find ${asset.trim() || "[asset type]"} in ${area.trim() || "[area]"}. Return the exact locations, cite the tool evidence, and explain uncertainty.`;
}
export function scoreLabel(score: unknown): string {
  return typeof score === "number"
    ? "Rubric evaluation score"
    : "Evaluation not scored";
}
