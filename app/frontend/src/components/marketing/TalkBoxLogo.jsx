/**
 * The display wordmark used across Talk Box's public-facing marketing pages.
 */
export default function TalkBoxLogo({ className = "", compact = false }) {
  return (
    <span className={`talkbox-logo ${compact ? "talkbox-logo--compact" : ""} ${className}`}>
      <span className="talkbox-logo__word">Talk</span>
      <span className="talkbox-logo__mark" aria-hidden>
        🗣️
      </span>
      <span className="talkbox-logo__word">Box</span>
      <span className="sr-only">Talk Box</span>
    </span>
  );
}
