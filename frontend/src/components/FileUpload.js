import React, { useRef, useState } from "react";
import api from "@/lib/api";
import { API } from "@/lib/api";
import { toast } from "sonner";
import { Paperclip, FileText, File as FileIcon } from "@phosphor-icons/react";

export function FileUpload({ onUploaded, accept, label = "Attach file" }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);

  const pick = () => ref.current?.click();
  const handle = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api.post("/files/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      onUploaded(res.data);
      toast.success("File attached");
    } catch {
      toast.error("Upload failed");
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  };

  return (
    <>
      <input ref={ref} type="file" accept={accept} onChange={handle} className="hidden" data-testid="file-input" />
      <button
        type="button"
        data-testid="file-upload-button"
        onClick={pick}
        disabled={busy}
        className="flex items-center gap-2 border-2 border-dashed border-[#E4E4E7] hover:border-[#EA580C] px-3 py-2.5 text-sm font-semibold text-[#71717A] hover:text-[#EA580C] transition-colors duration-200 w-full justify-center disabled:opacity-50"
      >
        <Paperclip size={16} weight="bold" /> {busy ? "Uploading…" : label}
      </button>
    </>
  );
}

export function Attachment({ file }) {
  const href = `${API}/files/${file.path}`;
  const isPdf = (file.content_type || "").includes("pdf");
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      data-testid="attachment-link"
      className="inline-flex items-center gap-2 border border-[#E4E4E7] px-2 py-1 text-xs font-semibold hover:border-[#EA580C] hover:text-[#EA580C] transition-colors duration-200"
    >
      {isPdf ? <FileText size={14} weight="bold" /> : <FileIcon size={14} weight="bold" />}
      <span className="truncate max-w-[160px]">{file.filename || "file"}</span>
    </a>
  );
}
