import { Head } from "../components/UI";
import { useState } from "react";
import RecipientActivity from "../components/RecipientActivity";
import { TrackingDisclosure } from "../components/Tracking";

export default function Sent({ tick }) {
  const [source, setSource] = useState("sent");
  return (
    <>
      <Head
        title="Sent emails"
        desc="Search campaign submissions, Gmail acceptance, tracking signals and replies. Select a recipient to view the original email."
      />
      <div className="actions sent-tabs">
        <button
          className="btn btn-secondary"
          aria-pressed={source === "sent"}
          onClick={() => setSource("sent")}
        >
          Campaign messages
        </button>
        <button
          className="btn btn-secondary"
          aria-pressed={source === "sent-replies"}
          onClick={() => setSource("sent-replies")}
        >
          Replies sent
        </button>
      </div>
      <RecipientActivity
        key={source}
        tick={tick}
        source={source}
        title={
          source === "sent"
            ? "Campaign message history"
            : "Replies sent through OutreachDesk"
        }
      />
      <TrackingDisclosure />
    </>
  );
}
