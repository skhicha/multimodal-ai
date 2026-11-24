import { useNavigate } from "react-router-dom";
import { FileText } from "lucide-react";
import type { Citation } from "../lib/api";
import "./ChatBubble.css";

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  provider?: string;
  citations?: Citation[];
}

export function ChatBubble({ message }: { message: ChatMessage }) {
  const navigate = useNavigate();

  return (
    <div className={`chat-bubble-row ${message.role}`}>
      <div className={`chat-bubble ${message.role}`}>
        {message.role === "assistant" && message.provider && (
          <div className="chat-provider-tag">via {message.provider}</div>
        )}
        {message.text}
        {message.citations && message.citations.length > 0 && (
          <div className="chat-citations">
            {message.citations.map((c, i) => (
              <button
                key={`${c.media_id}-${i}`}
                className="chat-citation-chip"
                onClick={() =>
                  navigate(c.segment_start !== null ? `/media/${c.media_id}?t=${c.segment_start}` : `/media/${c.media_id}`)
                }
              >
                <FileText size={12} />
                {c.filename}
                {c.segment_start !== null ? ` @${c.segment_start.toFixed(1)}s` : ""}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
