import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icon";
import {
  readPreference,
  writePreference,
  readAccessibility,
  type Preferences,
} from "./preferences";
export function Disclosure({
  id,
  title,
  children,
  defaultOpen = false,
  accessory,
  badge,
  hidden = false,
}: {
  id: string;
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  accessory?: ReactNode;
  badge?: number | "dot"; // issues in this section (docs/evaluation-issues)
  hidden?: boolean;
}) {
  const [open, setOpen] = useState(
    () => readPreference(`section.${id}`, defaultOpen) === true,
  );
  if (hidden) return null;
  return (
    <section className={`disclosure ${open ? "is-open" : ""}`}>
      <div className="disclosure-heading">
        <button
          className="disclosure-title"
          aria-expanded={open}
          aria-controls={`section-${id}`}
          onClick={() =>
            setOpen((prev) => {
              writePreference(`section.${id}`, !prev);
              return !prev;
            })
          }
        >
          <span>{title}</span>
          {badge === "dot" ? (
            <span
              className="issue-badge dot"
              aria-label="Below full marks"
              role="img"
            />
          ) : badge ? (
            <span
              className="issue-badge"
              aria-label={`${badge} ${badge === 1 ? "issue" : "issues"}`}
            >
              {badge}
            </span>
          ) : null}
          <Icon name="chevron" size={15} />
        </button>
        {accessory}
      </div>
      {open && (
        <div className="disclosure-content" id={`section-${id}`}>
          {children}
        </div>
      )}
    </section>
  );
}
export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => {
      el?.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="native-modal"
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label={`Close ${title}`}
        >
          <Icon name="x" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function Accessibility({
  value,
  onChange,
  onClose,
}: {
  value: Preferences;
  onChange: (value: Preferences) => void;
  onClose: () => void;
}) {
  const update = (key: keyof Preferences, next: any) => {
    const v = { ...value, [key]: next };
    writePreference("accessibility", v);
    onChange(v);
  };
  return (
    <Dialog title="Accessibility & reading" onClose={onClose}>
      <p>
        Choose the display that works for you. Settings stay on this browser
        across runs and refreshes.
      </p>
      <div className="setting-list">
        <label>
          <span>
            <b>Dyslexia-friendly reading</b>
            <small>Verdana, more spacing, and left-aligned text.</small>
          </span>
          <input
            type="checkbox"
            checked={value.reading}
            onChange={(e) => update("reading", e.target.checked)}
          />
        </label>
        <label>
          <span>
            <b>Colour-safe palette</b>
            <small>
              Blue/orange map colours. Status labels and patterns stay visible.
            </small>
          </span>
          <input
            type="checkbox"
            checked={value.colour === "colour-safe"}
            onChange={(e) =>
              update("colour", e.target.checked ? "colour-safe" : "standard")
            }
          />
        </label>
        {(
          [
            ["contrast", "High contrast"],
            ["largeText", "Larger text"],
            ["reducedMotion", "Reduce motion"],
          ] as const
        ).map(([key, label]) => (
          <label key={key}>
            <b>{label}</b>
            <input
              type="checkbox"
              checked={value[key]}
              onChange={(e) => update(key, e.target.checked)}
            />
          </label>
        ))}
      </div>
      <button
        className="secondary"
        onClick={() => {
          writePreference("accessibility", {});
          onChange(readAccessibility());
        }}
      >
        Reset display settings
      </button>
      <p className="fine-print">
        No research data is saved in these preferences.
      </p>
    </Dialog>
  );
}
