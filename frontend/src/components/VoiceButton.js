import React, { useState, useRef } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Microphone, Stop } from "@phosphor-icons/react";

const LANGS = [
  { code: "auto", label: "Auto" },
  { code: "hi", label: "हिंदी" },
  { code: "ta", label: "தமிழ்" },
  { code: "ml", label: "മലയാളം" },
  { code: "kn", label: "ಕನ್ನಡ" },
  { code: "te", label: "తెలుగు" },
  { code: "mr", label: "मराठी" },
  { code: "bn", label: "বাংলা" },
  { code: "en", label: "English" },
];

export default function VoiceButton({ onResult, showLang = true, title = "Speak" }) {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("auto");
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data);
      mr.onstop = handleStop;
      mr.start();
      recorderRef.current = mr;
      setRecording(true);
    } catch {
      toast.error("Microphone access denied");
    }
  };

  const stop = () => {
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setRecording(false);
  };

  const handleStop = async () => {
    setBusy(true);
    try {
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      if (blob.size < 500) {
        toast.warning("Recording too short. Try again.");
        return;
      }
      const fd = new FormData();
      fd.append("file", blob, "clip.webm");
      fd.append("language", lang);
      const res = await api.post("/voice/transcribe", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 45000,
      });
      const text = (res.data.text || "").trim();
      if (text) onResult(text);
      else toast.warning("Couldn't hear anything. Try again.");
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message;
      if (err?.code === "ECONNABORTED" || (detail || "").includes("timeout")) {
        toast.error("Transcription timed out. Try a shorter clip.");
      } else if (err?.response?.status === 413) {
        toast.error("Recording is too large. Please keep it under 25 MB.");
      } else {
        toast.error("Transcription failed. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-1 shrink-0" data-testid="voice-button">
      {showLang && (
        <select
          data-testid="voice-language-select"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
          className="h-[42px] border-2 border-[#09090B] bg-white text-xs font-semibold px-1 outline-none hidden sm:block"
          title="Language"
        >
          {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
      )}
      <button
        type="button"
        data-testid="voice-record-button"
        onClick={recording ? stop : start}
        disabled={busy}
        title={title}
        className={`h-[42px] w-[42px] flex items-center justify-center border-2 transition-colors duration-200 ${
          recording ? "bg-[#DC2626] border-[#DC2626] text-white" : "border-[#09090B] text-[#09090B] hover:bg-[#EA580C] hover:border-[#EA580C] hover:text-white"
        } disabled:opacity-50`}
      >
        {busy ? <span className="w-2 h-2 bg-current block pulse-dot" /> : recording ? <Stop size={18} weight="fill" /> : <Microphone size={18} weight="fill" />}
      </button>
    </div>
  );
}
