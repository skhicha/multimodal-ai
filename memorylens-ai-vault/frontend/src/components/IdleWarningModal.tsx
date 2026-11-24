import { useEffect, useState } from "react";
import { IDLE_WARNING_MS } from "../hooks/useIdleTimeout";
import "./IdleWarningModal.css";

interface Props {
  onStayActive: () => void;
}

// Shown IDLE_WARNING_MS before useIdleTimeout logs the user out, so they
// get a chance to cancel it just by interacting (any click here counts).
export function IdleWarningModal({ onStayActive }: Props) {
  const [secondsLeft, setSecondsLeft] = useState(Math.round(IDLE_WARNING_MS / 1000));

  useEffect(() => {
    setSecondsLeft(Math.round(IDLE_WARNING_MS / 1000));
    const interval = setInterval(() => {
      setSecondsLeft((s) => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="idle-modal-overlay" role="dialog" aria-modal="true">
      <div className="idle-modal">
        <h2>Are you still there?</h2>
        <p>
          You've been inactive for a while. For your security, you'll be logged out in{" "}
          <strong>{secondsLeft}s</strong> unless you stay active.
        </p>
        <button type="button" className="idle-modal-btn" onClick={onStayActive}>
          Stay logged in
        </button>
      </div>
    </div>
  );
}
